---
name: docs
description: 'Универсальный навык документирования: создание и обновление README,
  docs/content и регламентов.'
---

# Docs

## Overview
Create or update project documentation with minimal duplication and clear traceability.

## Workflow
1. Confirm scope and audience.
   - Identify target docs (root README, module README, docs/content, runbook).
   - Ask 1 clarifying question if scope is unclear.

2. Load project rules.
   - Locate repo root from cwd and read AGENTS.md (section "Документация").
   - Check existing README and docs in the target module.

3. Choose the correct location.
   - Use references/structure.md to decide where content belongs.
   - Avoid duplicate text; prefer links.

4. Release notes & versioning (when applicable).
   - Use references/release-notes.md for the release log format and versioning policy.
   - Keep `docs/content/release.md` as a consumer-facing changelog only (no rules/templates).
   - Store rules/versioning/milestones in the project `AGENTS.md` and follow them.
   - Ensure /docs/release stays a single, role-agnostic page with current milestones.

5. Update content.
   - Keep commands accurate and runnable.
   - Never add secrets or real .env values.
   - If infra/config changes, update backend/README.md or module README as required.

6. Validate.
   - If docs/content/*.md changed, preview /docs using the local flow in AGENTS.md.
   - Verify links and anchors.

7. Report.
   - List updated files and required follow-ups.

## Routing
- If documentation work depends on issue tracking or ledger updates, use `intbridge:issues`.
- If the doc update is driven by a code review, use code-review to produce the review report.

## References
- references/structure.md
- references/release-notes.md
