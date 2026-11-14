# Advanced Programming in Python

**Warehouse and order-management desktop application, originating in Jyothesh Karnam's MSc Computer Science coursework at Keele University.** Explore the original Python implementations, the university brief and a separately maintained Tkinter/SQLite application.

| Academic context | Verified detail |
| --- | --- |
| Module | Advanced Programming in Python (CSC-40068) |
| Programme / year | MSc Computer Science, Keele University, 2023/24 |
| Final module result | **85%** |
| Credit | 15 CATS |

This is the final module result on the official transcript issued 15 January 2025. Later AI-assisted maintenance in November 2026 was not assessed for that mark. The `2024` repository suffix describes the academic year. See [academic provenance](docs/ACADEMIC_PROVENANCE.md) and the [evidence manifest](docs/MODULE_EVIDENCE.json).

## Find the material

| Material | Purpose |
| --- | --- |
| [Original assessment brief](docs/original/CSC-40068-Assessment-Brief.pdf) | University-authored six-page coursework requirements, preserved unchanged |
| [Assessment and project map](docs/ASSESSMENT_AND_PROJECT.md) | Original task, source locations and the maintained application's differences |
| [Earlier implementation](advancepython.py), [second version](advancepython2.py), [preserved third version](legacy/advancepython3_2024.py) | Coursework-era source for OOP, GUI, concurrency experiments, similarity and simulation |
| [Supported launcher](advancepython3.py) | Runs the maintained local desktop application |
| [Domain and storage](warehouse_core.py) / [desktop view](warehouse_gui.py) | Separate testable business rules, SQLite transactions and Tkinter callbacks |
| [Architecture](docs/ARCHITECTURE.md), [decisions](docs/ENGINEERING_DECISIONS.md), [support runbook](docs/SUPPORT_RUNBOOK.md) | Design, tradeoffs, diagnosis and recovery |

The historical sources remain unchanged in this update. They contain earlier dependencies and media references that are not all included. Use the supported launcher below rather than treating the old files as current installation instructions.

## Download and run the desktop application

[Download the source ZIP](https://github.com/jyotheshkar/MSc-CS-Advanced-Programming-in-Python-Keele-University-2024/archive/refs/heads/main.zip), extract it, and open a terminal in that directory. Install **Python 3.11 or later with Tkinter**. Tkinter is included with many Python installers; on Linux it may be supplied separately as `python3-tk`.

```bash
python advancepython3.py --data-dir ./demo-data
```

The GUI, SQLite store and CSV export require **no third-party Python packages**, API keys, images or GIF files. This is a desktop application run from source; no packaged installer or executable is currently published. For optional PDF reports, install the report adapter in a virtual environment:

```bash
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python advancepython3.py --data-dir ./demo-data
```

Without `--data-dir`, the database is stored outside the checkout in the platform's user-data directory. `WAREHOUSE_DATA_DIR` provides another override; an explicit command-line directory takes precedence. The file is `warehouse.sqlite3`. Use one application instance per data directory.

## Try a complete workflow

1. Add a synthetic product with quantity 5, then search by its name or generated ID.
2. Select it and create an order for 2 units. Available stock becomes 3 immediately.
3. Advance the order from `registered` to `queued`, then either cancel it to restore stock or advance it to `collected`.
4. Inspect the event history, export CSV, close the application and reopen with the same data directory to check persistence.

Collected and cancelled orders remain as history. A cancelled reservation restores stock once; repeating cancellation does not restore it again. The maintained model has **one product per order** and a stock ceiling of **1,000,000**, rather than reproducing every original assessment constraint. It does not implement the coursework's specification-similarity feature, timed 30-order simulation or automatic five-unit replenishment. The [assessment map](docs/ASSESSMENT_AND_PROJECT.md) makes that distinction explicit.

## Import historical product CSV deliberately

Use **Import legacy CSV** in the GUI, or import into an empty inventory from the terminal:

```bash
python advancepython3.py --data-dir ./import-demo --import-legacy-csv ./product_log.csv
```

The importer accepts comma- or semicolon-separated UTF-8 CSV, with or without a BOM, and unique `id`, `name`, `quantity` and `specifications` columns. Quoted fields can include delimiters and newlines. All rows are validated before one transaction writes anything. Invalid input leaves inventory, events and the input file unchanged. New database IDs are assigned; old order/text logs are not migrated. An inventory that already contains products is rejected to prevent accidental duplicate loading.

## Verify and inspect the engineering

```bash
python -m unittest discover -s tests -v
python advancepython3.py --smoke-test
```

The first command covers stock/order invariants, persistence, rollback, import/export, competing reservations and invalid inputs using synthetic temporary databases. The second needs a graphical display and closes after exercising real widgets and model wiring. PDF tests require the optional ReportLab adapter; filesystem-link checks may skip on restricted hosts. See [14 November verification](docs/verification/2026-11-14.md) for actual results and [the earlier report](docs/verification/2026-11-10.md) for the preceding maintenance.

SQLite commits each stock/order mutation and its event together. Foreign keys, monotonic IDs, terminal order states and explicit cancellation rules make state transitions reviewable. The 14 November update fixes legacy CSV delimiter detection with multiline fields and rejects booleans/noncanonical identifiers that SQLite could otherwise alias to an existing row.

## Scope

This is a local academic/portfolio application, with no Amazon, ASUS or external warehouse integration, authentication, hosted service or measured production deployment. SQLite serialization is useful protection for local transactions; it does not establish multi-operator desktop support or distributed execution. [The architecture](docs/ARCHITECTURE.md) describes the implemented boundary and future design choices.

The university brief retains Keele's authorship. The private transcript is excluded. Keele's [2023/24 programme specification, page 4](https://www.keele.ac.uk/media/keeleuniversity/sas/qa/pgtprogrammespecifications/pgtprogspecs2023-24/Programme-Specification-Computer-Science-Taught-Masters-2023-24.pdf) independently confirms the module title and credit.
