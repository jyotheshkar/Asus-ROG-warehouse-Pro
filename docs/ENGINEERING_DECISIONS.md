# Engineering decisions

Decision date: **10 November 2026**. These records explain current AI-assisted maintenance choices for an existing university project. They are not claims that these choices, tests or support processes existed in 2024.

## 1. Use a single SQLite source of truth

**Problem.** The earlier GUI mixed in-memory collections and separate text/CSV writes. Source inspection found a comma/semicolon reader/writer mismatch, loaded state overwritten during GUI initialization, and orders without matching durable lifecycle state. A stock update followed by a failed order save could leave contradictory state.

**Decision.** Store products, orders and events in SQLite and apply each accepted inventory/order change within one transaction. Derive reports from that state. Use a user data directory rather than the checkout for writable files.

**Alternative considered.** Patch each CSV write and store orders in a second file. This would preserve the original storage format but require implementing cross-file consistency, ID allocation and recovery logic independently.

**Tradeoff.** SQLite is in Python's standard library and supports local transactions, but introduces a database format and a migration boundary. A deliberate product-CSV importer validates all rows and requires an empty inventory; original CSVs remain unchanged. Historical order/text logs are not migrated. The desktop application is not a shared remote inventory service.

## 2. Separate the desktop from business rules

**Problem.** Earlier product/order methods depended on Tkinter initialization and modal dialogs, making data behaviour difficult to test independently.

**Decision.** Keep validation, inventory updates, order transitions and storage in `warehouse_core.py`. `warehouse_gui.py` handles input and presentation; `advancepython3.py` remains the supported launcher. Test the same core used by the desktop.

**Alternative considered.** Test only by clicking through the existing GUI. This would leave restart, rollback and rejected-operation behaviour slow to verify and sensitive to a display server.

**Tradeoff.** A small module boundary adds structure to a small application. Unit tests establish specific data behaviour, while a separate GUI smoke check is still required for window creation and wiring. Neither substitutes for complete manual usability testing.

## 3. Make order changes explicit and transactional

**Problem.** The earlier code had duplicate order-ID risks, multiple removal paths, delayed callbacks with stale variables, and a path that referenced `time_collected` before assignment. Repeating or reordering actions could alter stock incorrectly.

**Decision.** Use explicit supported transitions, durable identity and terminal states. Reserve stock when an order is accepted; restore it only when a pending order is cancelled. Repeating cancellation is an idempotent local no-op: it returns the existing cancelled order without additional stock or events. Persist each transition and its event together. Reject invalid transitions before mutation.

**Tradeoff.** The maintained workflow intentionally has fewer ambiguous actions than the historical demonstration. It does not implement a complete shipping system, partial fulfilment, returns or distributed idempotency.

## 4. Remove mandatory decorative assets and keep PDF optional

**Problem.** The original repository did not contain the logo, button images or animation required by the GUI. Its animation loop could also recurse when media could not be read. Multiple packages existed only to support these assets.

**Decision.** Use native Tkinter controls and text for the supported desktop. Keep core operations on the standard library. Allow optional PDF exports through ReportLab and retain CSV as a package-free export.

**Tradeoff.** The application gives up the original decorative presentation to make setup smaller and its failure behaviour easier to understand. A missing optional report dependency should explain how to enable that feature, while leaving the rest of the application usable.

## 5. Preserve coursework provenance and record new verification separately

**Decision.** Keep the historical assessment files, preserve the original third version under `legacy/advancepython3_2024.py`, and identify the maintained entry point. Date new maintenance, documentation and verification explicitly. Do not transfer a new test pass to historical source.

**Tradeoff.** The repository contains more than one implementation for historical inspection. The README therefore names one supported launch command. The original academic work and current assistance must both be represented accurately in portfolio discussions.

## 6. Refuse report destinations that alias live storage

**Problem.** Opening a CSV destination in write mode truncates it. A filename that looks separate can be a symbolic link or hard link to the database or a SQLite journal file. Independent review reproduced the hard-link case against synthetic state.

**Decision.** Before exporting, compare both resolved path and existing-file identity (`samefile`) against the database and its journal/WAL/shared-memory sidecars. Reject protected destinations before opening the output. Regression tests verify byte preservation and usable inventory after rejected direct, symbolic-link and hard-link exports.

**Tradeoff.** These checks prevent accidental alias selection in the local desktop workflow; they do not create an adversarial filesystem sandbox or a distributed storage guarantee.
