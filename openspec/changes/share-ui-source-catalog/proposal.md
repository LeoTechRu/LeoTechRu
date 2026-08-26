## Why

The existing `ui-ux-pro-max` source and the temporary `ui-mvp-sources` installation create competing UI-skill identities. One intData-owned, updateable skill is needed as the shared UI/UX authority for Codex and Hermes.

Specification level: **full**. Triggers: shared agent tooling, cross-host distribution and hard-cut identity migration across Codex/Hermes homes.

## What Changes

- **BREAKING** Rename the canonical Tools skill from `ui-ux-pro-max` to `intdata-ui-ux` with no permanent alias.
- Fold the live catalog for Beautiful UI, beUI, Rare UI, Transitions.dev and shadcn/ui into `intdata-ui-ux`.
- Make `/int/tools/codex/assets/codex-home/skills/intdata-ui-ux/**` the sole updateable source.
- Install the same commit-bound artifact for Codex and Hermes profiles `default` and `intfall` on VDS and Windows VM.
- Supersede the temporary `ui-mvp-sources` installations only after the replacement is validated in each cell.
- Keep source publication and every host/runtime/profile installation as separate acceptance layers.

## Capabilities

### New Capabilities

- `ui-source-catalog`: Canonical intData UI/UX skill identity, reference-driven MVP adaptation and cross-runtime distribution requirements.

### Modified Capabilities

None.

## Impact

- Canonical source: `codex/assets/codex-home/skills/intdata-ui-ux/**` in `/int/tools`.
- Predecessors: `ui-ux-pro-max` and temporary user-level `ui-mvp-sources`.
- Consumers: Codex and Hermes `default`/`intfall` on VDS and Windows VM.
- No product repository, product UI, service, database or production surface changes.
