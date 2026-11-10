"""Asset-free Tkinter UI for the maintained university warehouse prototype."""
from __future__ import annotations

import argparse
import sqlite3
import sys
import tempfile
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from warehouse_core import Warehouse, WarehouseError


class WarehouseGUI(tk.Tk):
    def __init__(self, model):
        super().__init__()
        self.model = model
        self.title("Warehouse Pro | University project")
        self.geometry("1000x680")
        self.minsize(760, 500)
        self.status = tk.StringVar(value=f"Data: {model.database}")
        self.search = tk.StringVar()
        self._build()
        self.refresh()

    def _build(self):
        header = ttk.Frame(self, padding=12)
        header.pack(fill="x")
        ttk.Label(header, text="Inventory and Order Management", font=("TkDefaultFont", 16, "bold")).pack(side="left")
        ttk.Button(header, text="Refresh", command=lambda: self.perform(lambda: None)).pack(side="right")
        tabs = ttk.Notebook(self)
        tabs.pack(fill="both", expand=True, padx=12)
        inventory, orders, events = [ttk.Frame(tabs, padding=8) for _ in range(3)]
        for frame, title in [(inventory, "Inventory"), (orders, "Orders"), (events, "Event log")]:
            tabs.add(frame, text=title)
        search_bar = ttk.Frame(inventory)
        search_bar.pack(fill="x", pady=5)
        ttk.Label(search_bar, text="Search name or ID:").pack(side="left")
        entry = ttk.Entry(search_bar, textvariable=self.search)
        entry.pack(side="left", fill="x", expand=True, padx=8)
        entry.bind("<Return>", lambda event: self.perform(lambda: None))
        ttk.Button(search_bar, text="Search", command=lambda: self.perform(lambda: None)).pack(side="left")
        self.products = self._table(inventory, ("id", "name", "quantity", "specifications"),
                                    ("ID", "Product", "Available", "Specifications"))
        product_actions = ttk.Frame(inventory)
        product_actions.pack(fill="x", pady=8)
        for label, action in [("Add product", self.add_product), ("Receive stock", lambda: self.adjust_stock()),
                              ("Remove stock", lambda: self.adjust_stock(True)), ("Delete product", self.delete_product),
                              ("Create order", self.create_order)]:
            ttk.Button(product_actions, text=label, command=lambda f=action: self.perform(f)).pack(side="left", padx=3)
        reports = ttk.Frame(inventory)
        reports.pack(fill="x", pady=3)
        for label, action in [("Export CSV", lambda: self.export("csv")),
                              ("Inventory PDF", lambda: self.export("pdf")),
                              ("Zero-stock PDF", lambda: self.export("pdf", True)),
                              ("Import legacy CSV", self.import_legacy)]:
            ttk.Button(reports, text=label, command=lambda f=action: self.perform(f)).pack(side="left", padx=3)
        ttk.Label(orders, text="Select an order. Advance: registered → queued → collected. Cancellation restores stock once.").pack(anchor="w", pady=5)
        self.orders = self._table(orders, ("id", "product_name", "quantity", "status", "accepted_at", "collected_at"),
                                  ("ID", "Product", "Quantity", "Status", "Accepted (UTC)", "Collected (UTC)"))
        order_actions = ttk.Frame(orders)
        order_actions.pack(fill="x", pady=8)
        ttk.Button(order_actions, text="Advance selected order", command=lambda: self.perform(self.advance_order)).pack(side="left", padx=3)
        ttk.Button(order_actions, text="Cancel selected order", command=lambda: self.perform(self.cancel_order)).pack(side="left", padx=3)
        ttk.Label(events, text="Persisted events remain after closing the window. Use synthetic demonstration data.").pack(anchor="w", pady=5)
        self.events = self._table(events, ("id", "timestamp", "entity", "entity_id", "action", "details"),
                                  ("Event", "Time (UTC)", "Entity", "ID", "Action", "Details"))
        ttk.Label(self, textvariable=self.status, padding=10, wraplength=960).pack(fill="x")

    @staticmethod
    def _table(parent, columns, titles):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        table = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        vertical = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=table.xview)
        table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        table.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        for column, title in zip(columns, titles):
            table.heading(column, text=title)
            table.column(column, width=65 if column in {"id", "quantity", "entity_id"} else 180, minwidth=60)
        return table

    def refresh(self):
        for table, rows in [(self.products, self.model.list_products(self.search.get())),
                            (self.orders, self.model.list_orders()), (self.events, self.model.list_events())]:
            table.delete(*table.get_children())
            for row in rows:
                table.insert("", "end", iid=str(row["id"]), values=[row.get(column, "") if row.get(column) is not None else "" for column in table["columns"]])

    @staticmethod
    def selected_id(table):
        selection = table.selection()
        if not selection:
            raise WarehouseError("Select a row first.")
        return int(selection[0])

    def perform(self, action):
        try:
            action()
            self.refresh()
        except (WarehouseError, OSError, sqlite3.Error) as error:
            self.status.set(f"Action rejected: {error}")
            messagebox.showerror("Action could not be completed", str(error), parent=self)

    def _quantity(self, prompt):
        return simpledialog.askstring("Quantity", prompt, parent=self)

    def add_product(self):
        name = simpledialog.askstring("Add product", "Product name:", parent=self)
        if name is None:
            return
        quantity = self._quantity("Initial available quantity (zero or more):")
        if quantity is None:
            return
        specifications = simpledialog.askstring("Specifications", "Optional specifications:", parent=self)
        if specifications is None:
            return
        product = self.model.add_product(name, quantity, specifications)
        self.status.set(f"Created product #{product['id']}.")

    def adjust_stock(self, remove=False):
        product_id = self.selected_id(self.products)
        quantity = self._quantity("Quantity to remove:" if remove else "Quantity to receive:")
        if quantity is not None:
            self.model.adjust_stock(product_id, quantity, remove=remove)
            self.status.set(f"Adjusted stock for product #{product_id}.")

    def delete_product(self):
        product_id = self.selected_id(self.products)
        if messagebox.askyesno("Delete product", f"Delete product #{product_id}? Order history prevents deletion.", parent=self):
            self.model.delete_product(product_id)
            self.status.set(f"Deleted product #{product_id}.")

    def create_order(self):
        product_id = self.selected_id(self.products)
        quantity = self._quantity("Order quantity:")
        if quantity is not None:
            order = self.model.create_order(product_id, quantity)
            self.status.set(f"Created order #{order['id']}; stock reserved immediately.")

    def advance_order(self):
        order = self.model.advance_order(self.selected_id(self.orders))
        self.status.set(f"Order #{order['id']} is {order['status']}.")

    def cancel_order(self):
        order_id = self.selected_id(self.orders)
        if messagebox.askyesno("Cancel order", f"Cancel order #{order_id} and restore its stock?", parent=self):
            order = self.model.cancel_order(order_id)
            self.status.set(f"Order #{order['id']} is {order['status']}; stock restoration occurs only once.")

    def export(self, kind, zero_stock=False):
        path = filedialog.asksaveasfilename(parent=self, defaultextension="." + kind,
                                          filetypes=[(kind.upper(), "*." + kind)])
        if path:
            if kind == "csv":
                self.model.export_csv(path)
            else:
                self.model.export_pdf(path, zero_stock_only=zero_stock)
            self.status.set(f"Saved {kind.upper()} report.")

    def import_legacy(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("CSV files", "*.csv"), ("All files", "*")])
        if path:
            count = self.model.import_legacy_csv(path)
            self.status.set(f"Imported {count} products. Original CSV left unchanged.")


def smoke_test():
    """Exercise real widgets and model wiring without dialogs; needs a display."""
    with tempfile.TemporaryDirectory(prefix="warehouse-smoke-") as directory:
        model = Warehouse(directory)
        product = model.add_product("ASUS ROG synthetic demo", 5, "Synthetic smoke-test data")
        app = WarehouseGUI(model)
        try:
            app.update()
            assert len(app.products.get_children()) == 1
            app.products.selection_set(str(product["id"]))
            assert app.selected_id(app.products) == product["id"]
            order = model.create_order(product["id"], 2)
            app.refresh()
            assert len(app.orders.get_children()) == 1
            assert int(app.products.item(str(product["id"]), "values")[2]) == 3
            model.advance_order(order["id"])
            model.cancel_order(order["id"])
            app.refresh()
            assert int(app.products.item(str(product["id"]), "values")[2]) == 5
            assert app.orders.item(str(order["id"]), "values")[3] == "cancelled"
            app.search.set("no matching item")
            app.refresh()
            assert len(app.products.get_children()) == 0
            app.search.set("")
            app.refresh()
            app.update()
        finally:
            app.destroy()
    print("GUI smoke test passed (synthetic temporary data).")


def main(argv=None):
    parser = argparse.ArgumentParser(description="University warehouse prototype: local inventory and orders.")
    parser.add_argument("--data-dir", type=Path, help="Directory for warehouse.sqlite3; overrides WAREHOUSE_DATA_DIR.")
    parser.add_argument("--smoke-test", action="store_true", help="Self-closing synthetic GUI check; requires a display.")
    parser.add_argument("--import-legacy-csv", type=Path, help="Import a historical product CSV into an empty inventory, then exit.")
    args = parser.parse_args(argv)
    try:
        if args.smoke_test:
            smoke_test()
        else:
            model = Warehouse(args.data_dir)
            if args.import_legacy_csv:
                print(f"Imported {model.import_legacy_csv(args.import_legacy_csv)} products into {model.database}")
            else:
                WarehouseGUI(model).mainloop()
    except (OSError, sqlite3.Error, WarehouseError, tk.TclError) as error:
        print(f"Warehouse startup/action failed: {error}", file=sys.stderr)
        return 1
    return 0
