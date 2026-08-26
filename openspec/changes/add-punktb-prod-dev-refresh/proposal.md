# Change: Add PunktB prod to intdata dev refresh migrator

## Why
INT-332 needs a repeatable way to refresh the intdata dev database with the current PunktB production client state for testing, while guaranteeing that `punkt_b_prod` is only read through the read-only profile.

## What Changes
- Add an `intdb project-migrate punktb-prod-dev-refresh` workflow.
- Prefer source `punktb-prod-ro` when its grants allow export; allow `punktb-prod-migrator` only for source export sessions that intdb forces into `default_transaction_read_only=on`.
- Restrict target to `intdata-dev-admin` (`db_admin_dev`, database `intdata`) so the workflow can do a full replace of the approved dev table set.
- Export the currently readable assessment client-state table set from production with read-only `psql \copy (SELECT row_to_json(...))`: `assess.specialists`, `assess.clients`, `assess.diag_results`.
- Bootstrap the required `auth.users` and `auth.identities` rows inside dev from imported emails without copying prod auth state.
- Clean dependent dev-only rows that reference the refreshed records, then reload the target in one transaction with full-replace semantics for the approved table set.
- Support dry-run rollback and apply commit modes with report output.

## Impact
- Affected specs: `intdb`
- Affected code: `intdb/lib/intdb.py`, `intdb/tests/test_intdb.py`, `intdb/README.md`
- Runtime targets: source `punkt_b_prod` read-only; target `intdata` dev admin
- Issue: `INT-332`
