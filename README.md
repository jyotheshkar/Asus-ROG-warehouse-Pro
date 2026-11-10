# Warehouse and Order Management

A Python desktop inventory application originating in **Jyothesh Karnam's university coursework**. The repository retains the original 2024 assessment source. The supported application received a separate, AI-assisted maintenance update on **10 November 2026** to make its setup, persistence and troubleshooting behaviour reviewable.

## Supported application

- Add and search products, validate quantities and inspect available stock.
- Create orders, deduct stock, advance the order lifecycle and cancel eligible orders with stock restoration.
- Persist products, orders and timestamped events in a local SQLite database.
- Export inventory to CSV; optional ReportLab installation enables PDF reports.
- Run regression tests without opening a desktop window.

This is a local academic/personal portfolio application. It has no Amazon, Veeqo or ASUS integration, external customer deployment or measured production performance.

## Run

Use Python 3.11 or later with Tkinter support. Tkinter is supplied by many Python installers; Linux distributions may package it separately as `python3-tk`.

```bash
python advancepython3.py
```

No images, GIF files, API credentials or third-party Python packages are required for the core application. For optional PDF exports:

```bash
python -m venv .venv
# Activate .venv using the command for your shell.
python -m pip install -r requirements.txt
python advancepython3.py
```

The default database lives in a user data directory, outside the checkout. Override it with `WAREHOUSE_DATA_DIR` or an explicit directory:

```bash
python advancepython3.py --data-dir ./demo-data
```

The data file is `warehouse.sqlite3`. Use a fresh directory for demonstrations and keep real personal or business data out of this repository. Old product CSVs can be deliberately imported into an empty inventory using the GUI's **Import legacy CSV** action, or:

```bash
python advancepython3.py --data-dir ./import-demo --import-legacy-csv ./product_log.csv
```

The importer accepts comma/semicolon CSV with `id`, `name`, `quantity` and `specifications` columns, validates the complete file before writing and leaves the input file unchanged. It assigns new database IDs; it does not migrate old order/text logs. Preserve originals separately.

## Verify

```bash
python -m unittest discover -s tests -v
python advancepython3.py --smoke-test
```

The second command requires a working graphical display and closes after a short check of real widgets and their model wiring using temporary synthetic data. It does not cover every interactive workflow. Exact commands, observed results and limits are recorded in [the maintenance verification report](docs/verification/2026-11-10.md).

## Engineering and support evidence

| Document | Purpose |
|---|---|
| [Architecture](docs/ARCHITECTURE.md) | Components, data flow and order/stock invariants |
| [Engineering decisions](docs/ENGINEERING_DECISIONS.md) | Reasons, alternatives and tradeoffs behind the maintenance work |
| [Support runbook](docs/SUPPORT_RUNBOOK.md) | Fault reproduction, diagnosis, recovery and escalation details |
| [Verification](docs/verification/2026-11-10.md) | Executed checks and their scope |

The supported launcher is `advancepython3.py`; `warehouse_gui.py` contains its interface and `warehouse_core.py` contains business rules/storage. `advancepython.py`, `advancepython2.py` and `legacy/advancepython3_2024.py` preserve earlier coursework versions; they are historical source, not maintained launch commands. Some earlier media and local-file dependencies are absent from the original repository.

## Boundaries

SQLite keeps each inventory/order change and its event in one local transaction. This does not provide server hosting, authentication, distributed execution or a service-level guarantee. Use one desktop application instance per data directory. Source and tests can support descriptions of implemented functionality; they do not establish commercial outcomes or an individual's sole authorship of every change.
