## Context

See `proposal.md`. The Tools checkout already contains commit `919f820` with the five-source catalog and commit `51fa6d5` renaming the complete skill tree to `intdata-ui-ux`. The commits are local in an ahead range that must be reviewed before publication. VDS currently has temporary `ui-mvp-sources` copies, while Hermes `intfall` has a divergent partial `intdata-ui-ux` copy.

## Goals / Non-Goals

**Goals:**

- Maintain one complete, updateable intData UI/UX skill source.
- Preserve the existing search scripts and design datasets while adding live reference-driven component reuse.
- Distribute byte-equivalent commit-bound artifacts to all target cells.
- Remove predecessor identities only after replacement discovery and behavior are verified.

**Non-Goals:**

- Maintaining a second lightweight UI catalog skill.
- Selecting a product's visual language without an active product task.
- Adding services, MCP servers, credentials or product dependencies.
- Treating installation as proof that a product adopted a reference component.

## Decisions

### Use `intdata-ui-ux` as the only permanent identity

The directory name and `SKILL.md` frontmatter are both `intdata-ui-ux`. `ui-ux-pro-max` is the source predecessor and `ui-mvp-sources` is a temporary rollout artifact; neither remains as an alias after accepted migration.

Alternative: retain both skills for discoverability. Rejected because overlapping triggers waste context and allow their guidance to drift.

### Keep the full skill in Tools

The canonical source includes `SKILL.md`, search scripts and maintained data tables. The five live UI sources extend this skill instead of replacing its design reasoning and stack-specific knowledge.

Alternative: keep only the two-file temporary skill in user homes. Rejected because it has no durable update path and discards useful existing capability.

### Publish once, install by exact commit

Validate the complete skill tree, review the entire `origin/dev..HEAD` range, then publish the accepted Tools commits. Every Codex/Hermes installation derives from the same published commit and is compared using a normalized tree hash.

Alternative: maintain independently edited profile copies. Rejected because profile drift is already observable.

### Migrate each cell independently

For each VDS/Windows Codex or Hermes profile, install and verify `intdata-ui-ux` before retiring `ui-mvp-sources`. A failed or unreachable cell remains `NOT_VERIFIED` and retains its working predecessor until a later bounded attempt.

## Risks / Trade-offs

- [Shared ahead range contains unrelated commits] → Review every commit and changed path before publication; do not push a partial or unreviewed range.
- [Installed profile copy is incomplete] → Replace it from the exact canonical tree and compare normalized hashes.
- [Removing the predecessor breaks discovery] → Verify `intdata-ui-ux` in a fresh session before removing that cell's old directory.
- [Windows execution channel is unavailable] → Report Windows cells separately and do not infer installation from Desktop visibility.

## Migration Plan

1. Validate commits `919f820` and `51fa6d5`, the complete skill tree, search scripts and zero active `ui-ux-pro-max` source identity.
2. Review and publish the complete accepted Tools ahead range to `origin/dev`.
3. Install the published `intdata-ui-ux` tree into VDS Codex and Hermes `default`/`intfall`; verify discovery and hashes, then retire their temporary duplicates.
4. Repeat the same commit-bound migration for the three Windows cells through an observable host channel.
5. Roll back a failed cell by restoring its previously verified skill directory; source history is fixed forward rather than rewritten.
