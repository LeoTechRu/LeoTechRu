## Context

The first neutral cleanup utilities and compatibility wrappers exist, but the
package remains active until its exact Tools range is safely published. Later
high-risk candidates still contain product assumptions and are not part of this
slice.

## Goals / Non-Goals

**Goals:** establish neutral `repo-ops` ownership, preserve stable Punkt Б
entrypoints and make the catalog boundary explicit.

**Non-Goals:** bulk-moving gates/releases/browser/DBA tooling, deleting wrappers,
changing product runtime or making Tools the owner of Punkt Б policy.

## Decisions

- Neutral implementations live in `repo-ops`; Punkt Б paths remain thin
  compatibility wrappers. Duplicating implementations was rejected because the
  two paths would drift.
- Extraction proceeds only after product assumptions are parameterized and both
  entrypoints have checks. A bulk directory move was rejected as unreviewable.
- The public catalog identifies reusable ownership; product profiles/runbooks
  remain in the adapter.

## Migration Plan

1. Validate neutral entrypoints and compatibility wrappers together.
2. Publish the exact Tools range from a reconciled owning branch.
3. Inventory consumers before retiring any wrapper in a later change.
4. Extract another candidate only when its product assumptions and acceptance
   boundary are explicit.

## Rollback

Revert the neutral implementation and wrapper/catalog commit together. Do not
delete a legacy entrypoint; restore it to the last accepted implementation until
consumer migration is separately evidenced.

## Risks / Trade-offs

- [Wrapper and implementation drift] → wrapper delegates without business logic
  and both paths share smoke coverage.
- [Generic tool retains Punkt Б assumptions] → parameterize before extraction.
- [Divergent branch publishes an incomplete range] → reconcile and inspect the
  full ahead range before push.

## Evidence Layers

Source/tests, compatibility paths, catalog publication and downstream consumer
migration remain independent.
