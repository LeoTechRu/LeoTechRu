# Change: Reposition intTools As Public Tool Catalog

Owner: `/int/tools`.

Specification level: `full`.

Full triggers: public/private boundary, shared catalog governance,
cross-repository Web ownership and potentially destructive migration/removal.

## Why

`/int/tools` must be treated as an open-source public catalog of first-party tools, not as a mixed ops/runtime/reference storage area.

The current tree still contains public tools, private runtime machinery, legacy Codex overlays, copied references, and site content in one visible repository. That makes publication boundaries unclear and allows private or non-tool material to look like reusable public tooling.

## What Changes

- Define the public catalog taxonomy for `/int/tools`.
- Add a machine-readable catalog manifest that classifies every tracked non-hidden top-level directory.
- Add validation that blocks unclassified top-level public directories and forbidden public-repo artifacts.
- Rewrite the intTools README around public first-party tools and compatibility debt.
- Move the public website catalog surface to the master `web/tools` contour.
- Record legacy/reference destinations for content that must leave public tools before any destructive removal.
- State explicitly that IntBrain is outside intTools and must not be exposed through intTools MCP/search adapters.

## Scope Boundaries

- No repo split is performed in this change.
- No commit or push is part of this change.
- Destructive removals, untracking, or reference-submodule recreation require a separate owner approval after a dry-run diff.
- Runtime state, secrets, private governance, live host configs, and legacy Codex-home overlays must not be treated as public tool source.

## Issue

Historical provenance: retired `INT-357`; it is not an active lifecycle gate.

## Acceptance

- `tools.catalog.v1.json` exists and covers every tracked non-hidden top-level directory in `/int/tools`.
- Validation fails for missing manifest entries and forbidden public artifacts.
- README describes `intTools` as a public catalog, not a machine-wide ops/runtime repo.
- `web/tools` contains the public catalog site files and no longer advertises missing stored tools such as `openspec`, `punkt-b`, or `ngt-memory`.
- IntBrain search/fetch is not presented as an intTools public MCP surface.

Publication, cross-repository Web relocation and destructive cleanup remain
separate acceptance layers. This package records destinations but does not
authorize deletion, untracking, submodule recreation or root/Web mutation.
