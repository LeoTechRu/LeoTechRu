## 1. Canonical source hard cut

- [x] 1.1 Add the five-source live reference catalog to the complete Tools-owned UI skill in commit `919f820`.
- [x] 1.2 Rename the complete source tree and frontmatter from `ui-ux-pro-max` to `intdata-ui-ux` in commit `51fa6d5`.
- [x] 1.3 Run the skill validator, search-script checks and zero-scan for active `ui-ux-pro-max`/`ui-mvp-sources` references inside the canonical tree.

## 2. Source review and publication

- [x] 2.1 Review every commit and changed path in `origin/dev..HEAD`, including the pre-existing ahead range and foreign dirty state.
- [x] 2.2 Run strict OpenSpec validation, `git diff --check`, secret/generated-content review and `intnode coord commit-scope-check` for the exact publication set.
- [x] 2.3 Publish the accepted complete Tools commit range to `origin/dev`; do not rewrite or partially publish shared history.

## 3. VDS installation

- [x] 3.1 Install the published `intdata-ui-ux` artifact into VDS Codex and verify discovery, validator and normalized hash.
- [x] 3.2 Install the same artifact into VDS Hermes `default` and `intfall`; replace the divergent partial copy and verify both profiles.
- [x] 3.3 After replacement acceptance, retire the VDS `ui-mvp-sources` copies and prove only `intdata-ui-ux` remains.

## 4. Windows VM installation

- [ ] 4.1 Install the same commit-bound artifact into Windows Codex and verify discovery plus normalized hash.
- [ ] 4.2 Install it into Windows Hermes `default` and `intfall`, then verify both profiles independently.
- [ ] 4.3 After replacement acceptance, retire Windows predecessor copies and prove one identity per cell.

## 5. Acceptance receipts

- [x] 5.1 Record source, publication and all six runtime/profile cells separately as `PASS|FAIL|NOT_VERIFIED`.

## Acceptance receipt — 2026-08-26

Published source commit: `6522948c3fd7f1ca35cb437773ceecf8f85443c1`.
Normalized skill-tree SHA-256: `2535c0ce26043a261c1b54a58747a6a4cb22287522ca1acf7f0b77c02af9e6e1`.

| Cell | Status | Evidence |
|---|---|---|
| Canonical Tools source | PASS | Validator, reference/design-system/stack behavior and zero-scan pass. |
| `origin/dev` publication | PASS | Remote readback equals published source commit; the `dev` branch has no configured GitHub Actions run. |
| VDS Codex | PASS | Installed tree matches normalized hash; predecessor identity is absent. |
| VDS Hermes `default` | PASS | Enabled discovery, behavior check and normalized hash match. |
| VDS Hermes `intfall` | PASS | Enabled discovery, behavior check and normalized hash match. |
| Windows Codex | NOT_VERIFIED | No observable Windows execution channel used in this slice. |
| Windows Hermes `default` | NOT_VERIFIED | No observable Windows execution channel used in this slice. |
| Windows Hermes `intfall` | NOT_VERIFIED | No observable Windows execution channel used in this slice. |
