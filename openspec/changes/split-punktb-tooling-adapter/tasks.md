## 1. Spec and Inventory

- [x] Link the change to Multica issue `INT-348`.
- [x] Inventory `punkt-b/` and classify product-adapter content vs reusable tooling.
- [x] Define the target boundary between `punkt-b/` and reusable `repo-ops/`.

## 2. First Extraction Slice

- [x] Add `repo-ops/` as a top-level reusable repository-operations tool.
- [x] Move generic cleanup entrypoints to `repo-ops/bin/`.
- [x] Keep PunktB compatibility wrappers for moved cleanup utilities.
- [x] Fix stale `punctb` path in legacy sync tests.

## 3. Documentation and Catalog

- [x] Document `punkt-b/` as a product adapter, not a dumping ground for reusable scripts.
- [x] Document the next extraction candidates: gates/release/issue hooks, browser smoke, and DBA plans.
- [x] Add `repo-ops/` to README and public-safe website catalog.

## 4. Verification

- [x] Validate OpenSpec change strictly.
- [x] Run affected unit tests.
- [x] Smoke the moved `repo-ops` cleanup commands in dry-run mode.
- [ ] Verify git state, commit and publish to `origin/main`.
