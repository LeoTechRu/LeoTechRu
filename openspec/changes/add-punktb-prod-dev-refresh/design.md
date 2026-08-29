## Context

The source implementation exists, but live dry-run and canonical dev apply are
unfinished. The workflow crosses a production read boundary and a destructive
dev full-replace boundary, so source checks cannot establish runtime safety.

## Goals / Non-Goals

**Goals:** enforce fixed source/target profiles, guarantee source read-only
transactions, whitelist the replaced tables, keep target work atomic and report
evidence by layer.

**Non-Goals:** copying production auth state, expanding production grants,
writing production, refreshing non-whitelisted schemas or running without an
explicit target approval.

## Decisions

- Export with read-only `psql` queries rather than depend on `pg_dump` version
  compatibility. A migrator source role is admitted only with forced
  `default_transaction_read_only=on`.
- Recreate only required dev auth identities from imported emails; production
  auth tables and secrets are never read.
- Stage dependent cleanup and whitelisted reload in one target transaction.
  Partial commits and best-effort row merges were rejected because they leave an
  unverifiable hybrid dataset.
- Dry-run executes the target plan and rolls it back, rather than replacing DB
  evidence with a source-only plan printout.

## Migration Plan

1. Validate exact profiles, database/user identities and readable source scope.
2. Export the whitelisted production tables in a forced read-only session.
3. Execute the full target transaction in dry-run and record staged counts.
4. After separate apply authority, repeat the exact bundle and commit only after
   all invariants pass.
5. Verify target counts, relations and absence of source writes.

## Rollback

Dry-run always rolls back. Apply failures roll back the single target
transaction. After a successful commit, correction requires a newly reviewed
refresh or forward fix; the workflow never mutates production to compensate.

## Risks / Trade-offs

- [Source role has excess privilege] → force transaction read-only and verify
  identity before export.
- [Dependent dev rows retain stale references] → clean only declared dependants
  inside the same transaction.
- [Prod data scope expands silently] → fixed table whitelist and reported counts.
- [Auth identity collision] → deterministic dev-only bootstrap and transaction
  rollback on conflict.

## Evidence Layers

Source/tests, production read-only export, dev dry-run, canonical dev apply and
post-apply verification are recorded separately. No layer substitutes for
another.
