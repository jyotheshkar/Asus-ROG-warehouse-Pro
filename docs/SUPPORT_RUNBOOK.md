# Support and troubleshooting runbook

Applies to the maintained desktop application. The scenarios below are **reproduction procedures for this portfolio project**, not historical customer tickets.

## First checks

1. Record the commit, Python version, operating system, exact command and selected data directory.
2. Confirm the supported command is `python advancepython3.py`; the earlier assessment versions are historical.
3. Capture the error text and distinguish startup, validation, storage and optional-export failures.
4. Reproduce using synthetic products in a fresh `--data-dir` before considering any change to existing data.
5. Keep a copy of an affected database with the application closed. Do not delete it to hide a failure.

## Common faults

| Symptom | Diagnose | Safe action |
|---|---|---|
| `No module named tkinter` | Python was installed without Tk support | Install the operating system/Python distribution's Tk package, then run `python -m tkinter` |
| Display/`TclError` at startup | Session has no working graphical display | Run on a desktop; run core unit tests in headless environments |
| PDF feature unavailable | Optional ReportLab dependency is absent | Install `requirements.txt` in the selected virtual environment or use CSV export |
| Cannot create/open database | Data path is unwritable, is a regular file, or has restrictive permissions | Choose an owned writable directory; retain existing data and investigate permissions |
| Database locked | Another process may have the same local database open | Close the second application/process and retry; do not delete the database or journal files |
| Data appears missing after restart | Application may be using a different selected/default directory | Compare the original and current `--data-dir`/`WAREHOUSE_DATA_DIR`; reopen the correct directory |

## Reproduce stock and cancellation behaviour

Use a fresh demonstration directory. Add a synthetic product with quantity 5, then create an order for quantity 3. Expected available stock is 2.

Attempt another order for quantity 3. Expected result: a stock-validation error, no new order and available stock still 2. Cancel the first pending order. Expected stock returns to 5. Attempt to cancel it again. Expected result: the existing cancelled status is returned, stock remains 5 and no duplicate cancellation event is created.

If the result differs, record the product/order IDs, before/after quantities and action sequence. Escalate with those exact steps and the relevant regression-test result. Do not manually increase stock in the database to mask the defect.

## Reproduce order transitions and persistence

Create a new order, advance `registered` → `queued` → `collected`, and confirm stock is not restored. Attempt cancellation after collection or another transition from a terminal state. Expected result: rejection without a quantity change.

Close and reopen using the same data directory. Expected products, order status and events remain available. Run the regression suite if initialization appears to reset state:

```bash
python -m unittest discover -s tests -v
```

## Reproduce a storage-path failure safely

Create a disposable **regular file**, then pass its path to `--data-dir`. Because a file cannot contain `warehouse.sqlite3`, startup should fail with a storage/path error rather than showing a successfully initialized application. Remove only the disposable test file afterwards. For a real permission issue, choose another owned directory; do not run the application with administrator privileges as a routine workaround.

## Read-only database inspection

With the application closed, use a copy of the affected database. SQLite's `mode=ro` avoids a diagnostic session creating an empty replacement file:

```python
from pathlib import Path
import sqlite3

database = Path("/absolute/path/to/copy/warehouse.sqlite3").resolve()
connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
try:
    print(connection.execute("PRAGMA integrity_check").fetchall())
    print(connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall())
finally:
    connection.close()
```

`integrity_check` tests SQLite structural consistency; an `ok` result does not establish that all inventory business rules are correct. Apply schema-specific queries only after checking the current schema. Sanitize names, filesystem paths and any private data before sharing findings.

## Engineering escalation template

```text
Title: [operation] produces [observed result]
Revision and environment:
Supported command and selected data directory (sanitized):
Expected behaviour:
Observed behaviour and exact error:
Minimal steps using synthetic data:
Product/order IDs and before/after quantities:
Frequency and whether a fresh data directory reproduces it:
Relevant test command/result:
Evidence: sanitized traceback/event excerpts and screenshot if useful
Temporary workaround and its effect:
Data preservation: application closed; database copy retained
```

Include the smallest reliable reproduction, not a complete private database or credential-bearing environment dump. Record what remains unknown. A workaround is not a root-cause fix; rerun the reproducing case and affected regression tests after the engineering change.
