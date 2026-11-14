"""Regressions for ambiguous IDs and CSV parsing; all data is synthetic."""
import tempfile
import unittest
from pathlib import Path

from warehouse_core import Warehouse, WarehouseError


class ImportAndIdentifierTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = Warehouse(Path(self.directory.name) / "state")

    def test_noncanonical_product_ids_cannot_modify_another_product(self):
        product = self.store.add_product("Synthetic laptop", 5)
        before = self.store.list_products(), self.store.list_events()
        for invalid in [True, False, None, [], 1.0, "01", 0, -1, 2**63]:
            with self.subTest(invalid=invalid):
                with self.assertRaises(WarehouseError):
                    self.store.adjust_stock(invalid, 1)
        self.assertEqual((self.store.list_products(), self.store.list_events()), before)
        self.assertEqual(self.store.adjust_stock(str(product["id"]), 1)["quantity"], 6)

    def test_boolean_order_id_cannot_advance_first_order(self):
        product = self.store.add_product("Synthetic laptop", 5)
        order = self.store.create_order(product["id"], 1)
        before = self.store.list_orders(), self.store.list_events()
        with self.assertRaises(WarehouseError):
            self.store.advance_order(True)
        self.assertEqual((self.store.list_orders(), self.store.list_events()), before)
        self.assertEqual(self.store.advance_order(str(order["id"]))["status"], "queued")

    def test_malformed_imports_leave_inventory_and_events_unchanged(self):
        malformed = {
            "duplicate-header": "id,name,quantity,specifications,name\n1,Demo,2,ok,Other\n",
            "missing-field": "id,name,quantity,specifications\n1,Demo,2\n",
            "extra-field": "id,name,quantity,specifications\n1,Demo,2,ok,Extra\n",
            "unclosed-quote": 'id,name,quantity,specifications\n1,Demo,2,"unfinished\n',
        }
        for name, text in malformed.items():
            with self.subTest(name=name):
                path = Path(self.directory.name) / (name + ".csv")
                path.write_text(text, encoding="utf-8")
                original = path.read_bytes()
                with self.assertRaises(WarehouseError):
                    self.store.import_legacy_csv(path)
                self.assertEqual(self.store.list_products(), [])
                self.assertEqual(self.store.list_events(), [])
                self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
