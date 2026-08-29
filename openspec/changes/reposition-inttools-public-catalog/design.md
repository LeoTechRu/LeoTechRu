## Context

The manifest and public-catalog framing exist, while legacy/private/reference
material still needs owner-approved destinations. The active package therefore
remains a migration contract rather than evidence that cleanup has occurred.

## Goals / Non-Goals

**Goals:** make every public top-level entry classified, fail closed on forbidden
artifacts, keep IntBrain/private/runtime ownership outside public Tools and stage
cleanup from an explicit inventory.

**Non-Goals:** deleting or untracking content in this package, moving root/Web
state without their owning changes, or making `/int/tools` a private governance
authority.

## Decisions

- `tools.catalog.v1.json` is an inventory/validation input, not a second product
  requirements registry.
- Unknown tracked roots fail validation. Auto-classifying by path was rejected
  because a name cannot prove public safety or ownership.
- Legacy/private entries retain explicit status, destination and action until a
  separately approved move/removal. Immediate cleanup was rejected because the
  current repository contains compatibility and reference consumers.
- IntBrain adapters remain outside Tools; public catalog links may point to an
  owning product but do not proxy its authority.

## Migration Plan

1. Keep complete manifest coverage and forbidden-artifact validation green.
2. Verify each legacy/private entry's consumers and destination.
3. Execute each destructive or cross-repository move only through its separately
   approved owner change and exact dry-run diff.
4. Update the manifest after the owning move lands; archive only when no
   `legacy-remove` or unresolved migration action remains.

## Rollback

Before deletion, restore no state because no destructive action is authorized.
For an approved later move, rollback returns routing/catalog references to the
last accepted owning commit; deleted or untracked history must remain recoverable
from the reviewed Git range.

## Risks / Trade-offs

- [Manifest claims safety without inspecting content] → validation also checks
  forbidden tracked artifacts.
- [Public catalog becomes product authority] → entries declare owner/public
  surface and never absorb product requirements.
- [Cleanup breaks compatibility] → destination and consumer evidence precede
  every move.

## Evidence Layers

Inventory, validator/tests, Tools publication, Web ownership and destructive
migration receipts remain separate.
