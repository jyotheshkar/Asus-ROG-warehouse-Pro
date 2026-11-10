"""Local inventory/order model maintained separately from the Tkinter interface.

University-project maintenance, 10 November 2026, with AI assistance.
Only synthetic data should be used in public examples.
"""
from __future__ import annotations

import csv
import json
import os
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class WarehouseError(ValueError):
    """A rejected user action; state has not been changed."""


def default_data_dir() -> Path:
    """Store user data outside the checkout; an explicit override wins."""
    if os.environ.get("WAREHOUSE_DATA_DIR"):
        return Path(os.environ["WAREHOUSE_DATA_DIR"]).expanduser()
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "WarehousePro"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/WarehousePro"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "warehouse-pro"


def _integer(value, *, minimum=1) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise WarehouseError("Quantity must be a whole number.")
    try:
        result = int(value)
    except (ValueError, TypeError):
        raise WarehouseError("Quantity must be a whole number.") from None
    if isinstance(value, str) and str(result) != value.strip():
        raise WarehouseError("Quantity must be a whole number without decimals.")
    if result < minimum or result > 1_000_000:
        raise WarehouseError(f"Quantity must be between {minimum} and 1000000.")
    return result


def _text(value, label, *, optional=False):
    if not isinstance(value, str) or len(value.strip()) > 1000 or (not optional and not value.strip()):
        raise WarehouseError(f"{label} must contain between 1 and 1000 characters.")
    return value.strip()


class Warehouse:
    """One desktop application's SQLite store; no background workers or service."""

    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir).expanduser() if data_dir is not None else default_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.database = self.data_dir / "warehouse.sqlite3"
        with self._transaction() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity >= 0),
                specifications TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL)""")
            con.execute("""CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL REFERENCES products(id),
                quantity INTEGER NOT NULL CHECK(quantity > 0),
                status TEXT NOT NULL CHECK(status IN ('registered','queued','collected','cancelled')),
                accepted_at TEXT NOT NULL, collected_at TEXT)""")
            con.execute("""CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
                entity TEXT NOT NULL, entity_id INTEGER NOT NULL,
                action TEXT NOT NULL, details TEXT NOT NULL)""")

    @contextmanager
    def _transaction(self):
        con = sqlite3.connect(self.database, timeout=5)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _event(self, con, entity, entity_id, action, **details):
        con.execute("INSERT INTO events(timestamp,entity,entity_id,action,details) VALUES(?,?,?,?,?)",
                    (self._now(), entity, entity_id, action, json.dumps(details, sort_keys=True)))

    @staticmethod
    def _product(con, product_id):
        row = con.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        if row is None:
            raise WarehouseError("Product not found. Refresh inventory and check the product ID.")
        return dict(row)

    @staticmethod
    def _order(con, order_id):
        row = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if row is None:
            raise WarehouseError("Order not found. Refresh orders and check the order ID.")
        return dict(row)

    def add_product(self, name, quantity, specifications=""):
        name = _text(name, "Product name")
        quantity = _integer(quantity, minimum=0)
        specifications = _text(specifications, "Specifications", optional=True)
        with self._transaction() as con:
            cursor = con.execute("INSERT INTO products(name,quantity,specifications,updated_at) VALUES(?,?,?,?)",
                                 (name, quantity, specifications, self._now()))
            product_id = cursor.lastrowid
            self._event(con, "product", product_id, "created", quantity=quantity)
            return self._product(con, product_id)

    def list_products(self, query=""):
        query = _text(query, "Search", optional=True).casefold()
        with self._transaction() as con:
            rows = [dict(row) for row in con.execute("SELECT * FROM products ORDER BY id")]
        return [row for row in rows if not query or query in row["name"].casefold() or query == str(row["id"])]

    def adjust_stock(self, product_id, quantity, *, remove=False):
        quantity = _integer(quantity)
        with self._transaction() as con:
            product = self._product(con, product_id)
            new_quantity = product["quantity"] - quantity if remove else product["quantity"] + quantity
            if not 0 <= new_quantity <= 1_000_000:
                raise WarehouseError("Stock adjustment would exceed the available quantity or stock limit.")
            reserved = con.execute("SELECT COALESCE(SUM(quantity),0) FROM orders WHERE product_id=? AND status IN ('registered','queued')",
                                   (product_id,)).fetchone()[0]
            if new_quantity + reserved > 1_000_000:
                raise WarehouseError("Stock including active reservations cannot exceed 1000000.")
            con.execute("UPDATE products SET quantity=?,updated_at=? WHERE id=?", (new_quantity, self._now(), product_id))
            self._event(con, "product", product_id, "stock_removed" if remove else "stock_received", quantity=quantity)
            return self._product(con, product_id)

    def delete_product(self, product_id):
        with self._transaction() as con:
            self._product(con, product_id)
            if con.execute("SELECT 1 FROM orders WHERE product_id=?", (product_id,)).fetchone():
                raise WarehouseError("Products with order history cannot be deleted; keep the history for investigation.")
            con.execute("DELETE FROM products WHERE id=?", (product_id,))
            self._event(con, "product", product_id, "deleted")

    def create_order(self, product_id, quantity):
        quantity = _integer(quantity)
        with self._transaction() as con:
            product = self._product(con, product_id)
            if product["quantity"] < quantity:
                raise WarehouseError("Insufficient stock. Reduce the quantity or receive more stock first.")
            con.execute("UPDATE products SET quantity=quantity-?,updated_at=? WHERE id=?", (quantity, self._now(), product_id))
            cursor = con.execute("INSERT INTO orders(product_id,quantity,status,accepted_at) VALUES(?,?,'registered',?)",
                                 (product_id, quantity, self._now()))
            self._event(con, "order", cursor.lastrowid, "registered", product_id=product_id, quantity=quantity)
            return self._order(con, cursor.lastrowid)

    def list_orders(self):
        with self._transaction() as con:
            return [dict(row) for row in con.execute("""SELECT orders.*,products.name AS product_name
                FROM orders JOIN products ON products.id=orders.product_id ORDER BY orders.id""")]

    def advance_order(self, order_id):
        with self._transaction() as con:
            order = self._order(con, order_id)
            next_status = {"registered": "queued", "queued": "collected"}.get(order["status"])
            if next_status is None:
                raise WarehouseError("Collected and cancelled orders are final and cannot advance.")
            collected_at = self._now() if next_status == "collected" else None
            con.execute("UPDATE orders SET status=?,collected_at=? WHERE id=?", (next_status, collected_at, order_id))
            self._event(con, "order", order_id, next_status)
            return self._order(con, order_id)

    def cancel_order(self, order_id):
        with self._transaction() as con:
            order = self._order(con, order_id)
            if order["status"] == "cancelled":
                return order
            if order["status"] == "collected":
                raise WarehouseError("Collected orders cannot be cancelled; a physical return needs a separate process.")
            product = self._product(con, order["product_id"])
            if product["quantity"] + order["quantity"] > 1_000_000:
                raise WarehouseError("Restoring this order would exceed the stock limit.")
            con.execute("UPDATE products SET quantity=quantity+?,updated_at=? WHERE id=?",
                        (order["quantity"], self._now(), order["product_id"]))
            con.execute("UPDATE orders SET status='cancelled' WHERE id=?", (order_id,))
            self._event(con, "order", order_id, "cancelled", restored_quantity=order["quantity"])
            return self._order(con, order_id)

    def list_events(self):
        with self._transaction() as con:
            return [dict(row) for row in con.execute("SELECT * FROM events ORDER BY id")]

    def import_legacy_csv(self, path):
        """Explicitly import old product CSV once; reject all rows on any error."""
        with Path(path).open("r", encoding="utf-8-sig", newline="") as file:
            sample = file.read(4096)
            file.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;")
            except csv.Error:
                raise WarehouseError("Cannot identify a comma or semicolon CSV delimiter.") from None
            reader = csv.DictReader(file, dialect=dialect)
            if not {"id", "name", "quantity", "specifications"}.issubset(reader.fieldnames or []):
                raise WarehouseError("Legacy CSV must have id, name, quantity and specifications columns.")
            rows = []
            for line, row in enumerate(reader, start=2):
                try:
                    rows.append((_text(row["name"], "Product name"), _integer(row["quantity"], minimum=0),
                                 _text(row["specifications"], "Specifications", optional=True)))
                except WarehouseError as error:
                    raise WarehouseError(f"CSV row {line}: {error}") from error
        with self._transaction() as con:
            if con.execute("SELECT 1 FROM products LIMIT 1").fetchone():
                raise WarehouseError("Legacy import requires an empty inventory to prevent accidental duplicates.")
            for name, quantity, specifications in rows:
                cursor = con.execute("INSERT INTO products(name,quantity,specifications,updated_at) VALUES(?,?,?,?)",
                                     (name, quantity, specifications, self._now()))
                self._event(con, "product", cursor.lastrowid, "legacy_imported", quantity=quantity)
        return len(rows)

    def _report_path(self, path):
        path = Path(path)
        protected = [self.database] + [Path(str(self.database) + suffix) for suffix in ("-journal", "-wal", "-shm")]
        if path.resolve() in {item.resolve() for item in protected}:
            raise WarehouseError("Choose a report filename separate from the application's database.")
        # A different pathname can still refer to the same inode via a hard link.
        # Check identity before opening a report destination in truncating mode.
        if path.exists() and any(item.exists() and path.samefile(item) for item in protected):
            raise WarehouseError("Choose a report filename separate from the application's database.")
        return path

    def export_csv(self, path):
        with self._report_path(path).open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=["id", "name", "quantity", "specifications", "updated_at"])
            writer.writeheader()
            writer.writerows(self.list_products())

    def export_pdf(self, path, *, zero_stock_only=False):
        """Optional PDF adapter; inventory/order operations need no pip packages."""
        path = self._report_path(path)
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except ImportError:
            raise WarehouseError("PDF export requires ReportLab. Install requirements.txt or use CSV export.") from None
        from xml.sax.saxutils import escape
        styles = getSampleStyleSheet()
        rows = [row for row in self.list_products() if not zero_stock_only or row["quantity"] == 0]
        table_data = [["ID", "Product", "Available"]] + [
            [str(row["id"]), Paragraph(escape(row["name"]), styles["BodyText"]), str(row["quantity"])] for row in rows]
        table = Table(table_data, colWidths=[50, 350, 75], repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#176b68")),
                                  ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                  ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                                  ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        title = "Replenishment: zero-stock products" if zero_stock_only else "Warehouse inventory"
        SimpleDocTemplate(str(path), pagesize=A4).build([
            Paragraph(title, styles["Title"]), Spacer(1, 12), table])
