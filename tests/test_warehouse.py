"""Behavioural regressions for the maintained local warehouse application.

All data is synthetic; every test uses a temporary database/directory.
"""
import csv
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from warehouse_core import Warehouse, WarehouseError, default_data_dir


class WarehouseTests(unittest.TestCase):
    def test_report_export_rejects_hardlink_alias_of_database(self):
        self.product()
        alias = self.directory / "linked-report.csv"
        try:
            os.link(self.model.database, alias)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"Hard links unavailable: {error}")
        original = self.model.database.read_bytes()
        before = self.snapshot()
        for export in [self.model.export_csv, self.model.export_pdf]:
            with self.subTest(export=export.__name__):
                with self.assertRaises(WarehouseError):
                    export(alias)
                self.assertEqual(original, self.model.database.read_bytes())
                self.assertEqual(before, self.snapshot())

    def test_report_export_rejects_symlink_alias_of_database(self):
        self.product()
        alias = self.directory / "symlinked-report.csv"
        try:
            alias.symlink_to(self.model.database)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"Symbolic links unavailable: {error}")
        original = self.model.database.read_bytes()
        before = self.snapshot()
        for export in [self.model.export_csv, self.model.export_pdf]:
            with self.subTest(export=export.__name__):
                with self.assertRaises(WarehouseError):
                    export(alias)
                self.assertEqual(original, self.model.database.read_bytes())
                self.assertEqual(before, self.snapshot())

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="warehouse-test-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.model = Warehouse(self.directory / "state")

    def product(self, quantity=5, name="Synthetic laptop", specifications=""):
        return self.model.add_product(name, quantity, specifications)

    def snapshot(self):
        return (self.model.list_products(), self.model.list_orders(), self.model.list_events())

    def write_csv(self, filename="legacy.csv", delimiter=",", rows=None):
        path = self.directory / filename
        with path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=["id", "name", "quantity", "specifications"], delimiter=delimiter)
            writer.writeheader()
            writer.writerows(rows if rows is not None else [
                {"id": "ROG-001", "name": "Synthetic café laptop", "quantity": "5", "specifications": "screen; matte, bright\n16 GB"},
                {"id": "ROG-002", "name": "Synthetic keyboard", "quantity": "0", "specifications": "USB"},
            ])
        return path

    def test_restart_preserves_stock_orders_and_events(self):
        product = self.product(specifications="line one\nline two")
        order = self.model.create_order(product["id"], 2)
        self.model.advance_order(order["id"])
        expected = self.snapshot()
        reopened = Warehouse(self.model.data_dir)
        self.assertEqual(expected, (reopened.list_products(), reopened.list_orders(), reopened.list_events()))
        self.assertEqual(3, reopened.list_products()[0]["quantity"])
        self.assertEqual("queued", reopened.list_orders()[0]["status"])

    def test_invalid_product_quantities_leave_no_state(self):
        for quantity in [None, True, False, 1.5, -1, "-1", "1.5", "", "two", "01", 1_000_001]:
            with self.subTest(quantity=quantity):
                before = self.snapshot()
                with self.assertRaises(WarehouseError):
                    self.product(quantity)
                self.assertEqual(before, self.snapshot())

    def test_zero_initial_stock_is_valid_but_cannot_be_ordered(self):
        product = self.product(0)
        self.assertEqual(0, product["quantity"])
        before = self.snapshot()
        with self.assertRaises(WarehouseError):
            self.model.create_order(product["id"], 1)
        self.assertEqual(before, self.snapshot())

    def test_invalid_order_quantities_do_not_mutate_inventory_or_events(self):
        product = self.product()
        for quantity in [None, True, 1.1, -1, 0, "0", "1.0", "", "bad"]:
            with self.subTest(quantity=quantity):
                before = self.snapshot()
                with self.assertRaises(WarehouseError):
                    self.model.create_order(product["id"], quantity)
                self.assertEqual(before, self.snapshot())

    def test_insufficient_stock_has_no_partial_order_or_event(self):
        product = self.product(2)
        before = self.snapshot()
        with self.assertRaisesRegex(WarehouseError, "Insufficient stock"):
            self.model.create_order(product["id"], 3)
        self.assertEqual(before, self.snapshot())

    def test_cancel_restores_stock_once_and_repeat_adds_no_event(self):
        product = self.product(5)
        order = self.model.create_order(product["id"], 3)
        self.assertEqual(2, self.model.list_products()[0]["quantity"])
        cancelled = self.model.cancel_order(order["id"])
        self.assertEqual("cancelled", cancelled["status"])
        self.assertEqual(5, self.model.list_products()[0]["quantity"])
        after_first_cancel = self.snapshot()
        self.assertEqual(cancelled, self.model.cancel_order(order["id"]))
        self.assertEqual(after_first_cancel, self.snapshot())

    def test_queued_order_can_be_cancelled(self):
        product = self.product()
        order = self.model.create_order(product["id"], 2)
        self.model.advance_order(order["id"])
        self.model.cancel_order(order["id"])
        self.assertEqual(5, self.model.list_products()[0]["quantity"])

    def test_collect_is_final_with_timestamp_and_no_stock_restoration(self):
        product = self.product()
        order = self.model.create_order(product["id"], 2)
        queued = self.model.advance_order(order["id"])
        self.assertEqual("queued", queued["status"])
        self.assertIsNone(queued["collected_at"])
        collected = self.model.advance_order(order["id"])
        self.assertEqual("collected", collected["status"])
        self.assertIsNotNone(collected["collected_at"])
        self.assertTrue(collected["accepted_at"].endswith("+00:00"))
        self.assertTrue(collected["collected_at"].endswith("+00:00"))
        self.assertEqual(3, self.model.list_products()[0]["quantity"])
        before = self.snapshot()
        for action in [self.model.advance_order, self.model.cancel_order]:
            with self.assertRaises(WarehouseError):
                action(order["id"])
            self.assertEqual(before, self.snapshot())

    def test_cancelled_order_cannot_advance(self):
        product = self.product()
        order = self.model.create_order(product["id"], 1)
        self.model.cancel_order(order["id"])
        before = self.snapshot()
        with self.assertRaises(WarehouseError):
            self.model.advance_order(order["id"])
        self.assertEqual(before, self.snapshot())

    def test_stock_removal_cannot_oversell_or_exceed_stock_limit(self):
        product = self.product(3)
        self.model.adjust_stock(product["id"], 2, remove=True)
        self.assertEqual(1, self.model.list_products()[0]["quantity"])
        for quantity, remove in [(2, True), (1_000_000, False), (0, True)]:
            before = self.snapshot()
            with self.assertRaises(WarehouseError):
                self.model.adjust_stock(product["id"], quantity, remove=remove)
            self.assertEqual(before, self.snapshot())

    def test_receiving_stock_preserves_capacity_for_pending_cancellation(self):
        product = self.product(1_000_000)
        order = self.model.create_order(product["id"], 2)
        before = self.snapshot()
        with self.assertRaisesRegex(WarehouseError, "active reservations"):
            self.model.adjust_stock(product["id"], 1)
        self.assertEqual(before, self.snapshot())
        self.model.cancel_order(order["id"])
        self.assertEqual(1_000_000, self.model.list_products()[0]["quantity"])

    def test_product_ids_not_reused_after_deletion(self):
        first = self.product()
        self.model.delete_product(first["id"])
        second = self.product()
        self.assertGreater(second["id"], first["id"])

    def test_order_ids_not_reused_after_cancellation(self):
        product = self.product()
        first = self.model.create_order(product["id"], 1)
        self.model.cancel_order(first["id"])
        reopened = Warehouse(self.model.data_dir)
        second = reopened.create_order(product["id"], 1)
        self.assertGreater(second["id"], first["id"])

    def test_order_history_prevents_product_deletion(self):
        product = self.product()
        order = self.model.create_order(product["id"], 1)
        self.model.cancel_order(order["id"])
        before = self.snapshot()
        with self.assertRaisesRegex(WarehouseError, "order history"):
            self.model.delete_product(product["id"])
        self.assertEqual(before, self.snapshot())

    def test_failed_event_write_rolls_back_order_and_stock(self):
        product = self.product()
        before = self.snapshot()
        with patch.object(self.model, "_event", side_effect=RuntimeError("synthetic write failure")):
            with self.assertRaisesRegex(RuntimeError, "synthetic write failure"):
                self.model.create_order(product["id"], 3)
        self.assertEqual(before, self.snapshot())

    def test_two_simultaneous_reservations_cannot_oversell(self):
        product = self.product(5)
        barrier = threading.Barrier(2)
        results = []
        unexpected = []

        def reserve():
            try:
                model = Warehouse(self.model.data_dir)
                barrier.wait(timeout=5)
                try:
                    model.create_order(product["id"], 4)
                    results.append("created")
                except WarehouseError:
                    results.append("rejected")
            except BaseException as error:
                unexpected.append(error)

        threads = [threading.Thread(target=reserve) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual([], unexpected)
        self.assertCountEqual(["created", "rejected"], results)
        self.assertEqual(1, self.model.list_products()[0]["quantity"])
        self.assertEqual(1, len(self.model.list_orders()))
        self.assertEqual(2, len(self.model.list_events()))

    def test_legacy_import_handles_comma_and_semicolon_utf8_multiline(self):
        for delimiter in [",", ";"]:
            with self.subTest(delimiter=delimiter):
                model = Warehouse(self.directory / ("comma" if delimiter == "," else "semicolon"))
                path = self.write_csv(filename="comma.csv" if delimiter == "," else "semicolon.csv", delimiter=delimiter)
                original_bytes = path.read_bytes()
                self.assertEqual(2, model.import_legacy_csv(path))
                self.assertEqual(original_bytes, path.read_bytes())
                products = model.list_products()
                self.assertEqual("Synthetic café laptop", products[0]["name"])
                self.assertEqual("screen; matte, bright\n16 GB", products[0]["specifications"])
                self.assertEqual([5, 0], [product["quantity"] for product in products])
                self.assertEqual(2, len(model.list_events()))

    def test_invalid_second_csv_row_import_is_atomic(self):
        path = self.write_csv(rows=[
            {"id": "ROG-001", "name": "Valid synthetic item", "quantity": "5", "specifications": "ok"},
            {"id": "ROG-002", "name": "Invalid synthetic item", "quantity": "-2", "specifications": "bad"},
        ])
        before = self.snapshot()
        with self.assertRaisesRegex(WarehouseError, "CSV row 3"):
            self.model.import_legacy_csv(path)
        self.assertEqual(before, self.snapshot())

    def test_import_rejects_duplicate_load_without_mutation(self):
        path = self.write_csv()
        self.model.import_legacy_csv(path)
        before = self.snapshot()
        with self.assertRaisesRegex(WarehouseError, "empty inventory"):
            self.model.import_legacy_csv(path)
        self.assertEqual(before, self.snapshot())

    def test_csv_export_roundtrips_unicode_and_multiline_fields(self):
        product = self.product(name="Synthetic café laptop", specifications="one, two; three\nsecond line")
        path = self.directory / "export.csv"
        self.model.export_csv(path)
        with path.open(encoding="utf-8", newline="") as file:
            rows = list(csv.DictReader(file))
        self.assertEqual(1, len(rows))
        self.assertEqual(str(product["id"]), rows[0]["id"])
        self.assertEqual("Synthetic café laptop", rows[0]["name"])
        self.assertEqual("one, two; three\nsecond line", rows[0]["specifications"])
        self.assertEqual("5", rows[0]["quantity"])

    def test_report_export_cannot_overwrite_database_or_journal_paths(self):
        self.product()
        before = self.snapshot()
        original_database = self.model.database.read_bytes()
        for suffix in ["", "-journal", "-wal", "-shm"]:
            target = Path(str(self.model.database) + suffix)
            for export in [self.model.export_csv, self.model.export_pdf]:
                with self.subTest(suffix=suffix, export=export.__name__):
                    with self.assertRaises(WarehouseError):
                        export(target)
                    self.assertEqual(before, self.snapshot())
                    self.assertEqual(original_database, self.model.database.read_bytes())

    @unittest.skipUnless(importlib.util.find_spec("reportlab"), "optional ReportLab is not installed")
    def test_pdf_inventory_and_zero_stock_export_produce_pdf_documents(self):
        self.product(5)
        self.product(0, name="Synthetic replenishment item")
        for zero_stock_only in [False, True]:
            path = self.directory / ("zero-stock.pdf" if zero_stock_only else "inventory.pdf")
            self.model.export_pdf(path, zero_stock_only=zero_stock_only)
            self.assertEqual(b"%PDF", path.read_bytes()[:4])
            self.assertGreater(path.stat().st_size, 1000)

    def test_unknown_products_and_orders_do_not_change_state(self):
        product = self.product()
        before = self.snapshot()
        actions = [lambda: self.model.create_order(999, 1), lambda: self.model.adjust_stock(999, 1),
                   lambda: self.model.delete_product(999), lambda: self.model.advance_order(999),
                   lambda: self.model.cancel_order(999)]
        for action in actions:
            with self.assertRaises(WarehouseError):
                action()
            self.assertEqual(before, self.snapshot())
        self.assertEqual(product["id"], self.model.list_products()[0]["id"])

    def test_search_supports_casefold_name_and_exact_product_id(self):
        product = self.product(name="Synthetic Café Laptop")
        self.assertEqual([product], self.model.list_products("CAFÉ"))
        self.assertEqual([product], self.model.list_products(str(product["id"])))
        self.assertEqual([], self.model.list_products("missing"))

    def test_explicit_data_directory_overrides_environment(self):
        with patch.dict(os.environ, {"WAREHOUSE_DATA_DIR": str(self.directory / "environment")}):
            self.assertEqual(self.directory / "environment", default_data_dir())
            explicit = Warehouse(self.directory / "explicit")
            self.assertEqual(self.directory / "explicit", explicit.data_dir)
            self.assertFalse((self.directory / "environment").exists())

    def test_startup_regular_file_data_path_fails_cleanly(self):
        invalid_path = self.directory / "not-a-directory"
        invalid_path.write_text("synthetic marker", encoding="utf-8")
        launcher = Path(__file__).resolve().parents[1] / "advancepython3.py"
        result = subprocess.run([sys.executable, str(launcher), "--data-dir", str(invalid_path)],
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Warehouse startup/action failed:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual("synthetic marker", invalid_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
