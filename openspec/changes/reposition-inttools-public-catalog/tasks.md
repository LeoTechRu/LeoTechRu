## 1. Governance and Taxonomy

- [x] Create `reposition-inttools-public-catalog` OpenSpec change.
- [x] Define taxonomy statuses for public tools, public adapters, catalog links, master-private content, runtime state, and legacy removals.
- [x] Record that IntBrain is outside intTools.

## 2. Manifest and Validation

- [x] Add `tools.catalog.v1.json`.
- [x] Add validation for tracked non-hidden top-level directories.
- [x] Add forbidden artifact checks for public intTools source.

## 3. Documentation and Website

- [x] Rewrite `tools/README.md` as a public catalog entrypoint.
- [x] Add master `web/tools` catalog site files.
- [x] Remove missing stored-tool entries from public site metadata.

## 4. Deferred Cleanup

- [ ] Dry-run deletion or migration for legacy/reference/vendor content.
- [ ] Move `gemini-openai-proxy` to a master read-only reference submodule after approval.
- [ ] Remove legacy Codex-home/project overlays after approval.
- [ ] Split or remove `chatgpt-apps/int-tools-mcp` after destination approval.

## 5. Verification

- [x] Validate OpenSpec change.
- [x] Validate catalog manifest coverage.
- [x] Run focused unit tests for first public-tool batch.
- [x] Verify website catalog syntax and JSON load from `web/tools`.
- [ ] Remove or untrack forbidden legacy artifacts only under exact destructive
      approval; record destination, recoverability and owning commit separately.
