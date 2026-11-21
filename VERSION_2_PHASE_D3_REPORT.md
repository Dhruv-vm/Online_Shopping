# Version 2.0 — Phase D3: Test-Database Isolation

## Problem
The suite reused one `*_test` database across runs, so leftover rows from earlier runs could
change results. Overlapping runs on the same database broke each other: Phase C saw spurious
price-sync and reservation failures that way.

## Change (`backend/tests/conftest.py`)
1. **Clean start every session.** Drop the dedicated test database (`DROP DATABASE … WITH (FORCE)`),
   recreate it, run all Alembic migrations to head, and seed the baseline catalogue once.
2. **Never touches real data.** The database name must contain `test`, and `basket_db`,
   `basket_shared_demo` and `postgres` are refused outright. The name comes from
   `TEST_DATABASE_URL`, or the configured database with `_test` appended.
3. **One run at a time.** A per-database file lock (`$TMPDIR/basket-pytest-<db>.lock`, `flock`).
   A second run stops immediately with "Another test run is using basket_db_test …"; it does
   not drop the database under the first run. Verified live.
4. **Fast iteration preserved.** `BASKET_TEST_SKIP_MIGRATE=1` reuses the existing test database
   (no drop or migrate). The gate never sets it.

## Acceptance (frozen code, HEAD at the end of the final cycle, 21 Nov 2026)

| Run | Result | Time |
|---|---|---|
| Full suite #1 (fresh database) | **604 passed**, 3 skipped, 0 failed | 138 s |
| Full suite #2 | **604 passed**, 3 skipped, 0 failed | 125 s |
| Full suite #3 | **604 passed**, 3 skipped, 0 failed | 118 s |
| Targeted run (6 final-cycle files) | **14 passed** | 6 s |
| Full suite #4 (after the targeted run) | **604 passed**, 3 skipped, 0 failed | 126 s |

No order-dependent failures. The 3 skips are pre-existing, environment-dependent tests.

An earlier provisional sequence ran while code was still changing. Its single failure was the
migration-head pin, updated after a new migration landed mid-run. That sequence is superseded by
the one above.

## Note for tooling
`scripts/audit-features.sh` is a bash script (it relies on word splitting). Run it with `bash`
or directly, not `zsh scripts/audit-features.sh`.
