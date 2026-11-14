# Assessment and project map

Source: [original CSC-40068 assessment brief](original/CSC-40068-Assessment-Brief.pdf), six pages, deadline **5 January 2024**. It is university-authored material. This guide is a new November 2026 reading aid, not a replacement brief or an assessment of the submission.

## The original task

The brief allocates 50% to an object-oriented GUI warehouse application, 20% to concurrency/parallelism improvements, 20% to a timed workflow simulation and 10% to a code demonstration. It asks for product search and stock management, PDF inventory/shopping reports, specification similarity, order lifecycle logging, a launchable icon, concurrent operatives and a simulation accepting 30 orders from JSON. Its simulated warehouse holds at most five units of each product and replenishes out-of-stock items. The final **85% module mark** is verified separately; no component marks are inferred.

## What to review, and what to run

| Area | Original source evidence | Maintained application today |
| --- | --- | --- |
| OOP and desktop UI | Classes and Tkinter views in all three earlier implementations | `Warehouse` model in `warehouse_core.py`; `WarehouseGUI` in `warehouse_gui.py` |
| Product search and stock | Earlier add/remove/search methods | Search by case-folded name or exact ID; validated receive/remove operations |
| Product similarity | Similarity-processing methods in `advancepython2.py` and `legacy/advancepython3_2024.py` | Not implemented in the supported model |
| Reports and logs | Earlier PDF methods and file-based logs | CSV and optional ReportLab PDFs; transactional timestamped SQLite events |
| Orders | Earlier multiple-product list workflow | One product per order; registered, queued, collected or cancelled; terminal history retained |
| Concurrency and simulation | Thread-pool use and `simulate_orders` in the preserved third version | No timed 30-order simulator or background operative workers; SQLite serializes local write transactions |
| Stock/replenishment | Coursework maximum of five and a shopping-list workflow | Manual stock adjustments up to 1,000,000; zero-stock report; no automatic purchasing |
| Launching | Original media/local-file dependencies are incomplete in this checkout | Standard-library launcher `python advancepython3.py`; optional PDF package; no published installer |

Source presence establishes inspectable implementation attempts, not successful execution or full compliance with each original requirement. The historical versions remain unmodified so their approach and limitations can be reviewed. Run the maintained launcher for a reproducible demonstration; do not install guessed dependencies merely to make an unsupported historical version start.

## System design decisions in the maintained edition

The supported application separates UI callbacks, business invariants and persistence. Each product/order change and its event share a SQLite transaction. Inventory cannot become negative; cancellation restores reserved stock once; order IDs are not reused; records with order history cannot be deleted. Existing regressions inject a failed event write to prove rollback, reopen the store to verify persistence and race two reservations to check that only one succeeds when stock is insufficient.

This deliberate local application is not a distributed warehouse platform or a reimplementation of every simulation rule. For multi-product orders, add an `order_lines` table and reserve all lines atomically. For a simulation, keep deterministic scheduling and simulated time separate from GUI callbacks, define FIFO acceptance explicitly and test the five-unit capacity rule. Those are future changes, not capabilities claimed by this update.
