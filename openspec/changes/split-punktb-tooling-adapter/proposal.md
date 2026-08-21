# Change: Split PunktB Adapter From Universal Tooling

## Why

`punkt-b/` currently mixes several different concerns:

- PunktB-specific migration, DBA, Supabase/backend, QA and runbook adapters;
- reusable repo workflow scripts for issue, gate, release and hook handling;
- generic cleanup utilities;
- historical DB plans and product-specific skills.

That makes the root catalog misleading: `punkt-b/` looks like one tool, while parts of it are reusable intTools capabilities that should not stay tied to one product adapter.

## What Changes

- Introduce `repo-ops/` as the neutral home for reusable repository operations helpers.
- Keep `punkt-b/` as a product adapter with wrappers, profiles, product runbooks and product-specific smoke scenarios.
- Move the first generic cleanup utilities out of `punkt-b/ops/qa/` into `repo-ops/bin/`.
- Preserve backward-compatible PunktB wrappers for the moved utilities.
- Fix stale hardcoded `punctb` path references in PunktB tests.
- Update the public-safe tools catalog and README to show `repo-ops/` as its own catalog unit.
- Document the remaining PunktB split plan without moving high-risk gate/release/browser scripts in this first slice.

## Scope Boundaries

- No secrets, local private paths, private hostnames, credentials, or personal data are added.
- No product-core code is moved into `/int/tools`.
- No production or dev runtime state is changed.
- Existing PunktB wrappers remain callable during this phase.
- Gate, release and browser-smoke script extraction is planned but not bulk-moved until those scripts are parameterized away from PunktB-specific assumptions.

## Issue

Owning Multica issue: `INT-348`.

## Acceptance

- `repo-ops/` exists as a visible top-level catalog unit.
- Generic cleanup utilities have neutral `repo-ops/bin/` entrypoints.
- `punkt-b/ops/qa/agent_tmp_cleanup.py` and `punkt-b/ops/qa/agent_lock_cleanup.py` remain compatibility wrappers.
- `punkt-b/tests/test_legacy_assess_sync.py` no longer imports from the stale `punctb` path.
- README and website catalog describe `repo-ops/` and the narrowed purpose of `punkt-b/`.
- OpenSpec validation and relevant unit/smoke checks pass.
