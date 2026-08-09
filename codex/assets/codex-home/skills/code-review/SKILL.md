---
name: code-review
description: Универсальный код-ревью с фиксацией отчета в OpenSpec+GitHub Issues при наличии
  замечаний и чек-листами по стеку.
---

# Code Review

## Overview

Perform a structured code review for the current repo and record results in OpenSpec+GitHub Issues.
Все ответы и сам отчёт пишите на русском языке.

## Workflow

1. Confirm scope and inputs.
   - Identify the files, diff, branch, or feature to review.
   - Ask a short clarifying question if scope is unclear.
   - Do not modify code unless explicitly requested.

2. Load project rules.
   - Locate repo root from cwd and read AGENTS.md (or GEMINI.md) for process constraints.
   - Load references/project-rules.md for review-specific reminders.

3. Select domain checklists (load only what applies).
   - React/UI in web/**: references/review-react.md
   - Supabase Edge in backend/supabase/functions/**: references/review-supabase-edge.md
   - Postgres SQL in backend/supabase/migrations/** or SQL files: references/review-postgres.md
   - Add more stack references as needed (keep them generic, not project-bound).

4. Review execution.
   - Prioritize correctness, security, regressions, and missing tests.
   - Capture evidence with file path and line number.
   - Rank findings by severity (critical/high/medium/low/nit).

5. Fix results in OpenSpec+GitHub Issues (только если есть замечания).
   - Запиши выводы в GitHub Issues (worklog/комментарий) с ссылками на файлы/строки.
   - Если нужны изменения требований/поведения — создай/обнови OpenSpec-дельту.

6. Respond.
   - If issues exist: summarize top issues first, then open questions.
   - If no issues: respond that there are no remarks; do not create any files.
   - Mention tests run/not run.

## Routing
- If the review requires E2E or test generation, use playwright-testing. If it requires live browser-proof, visual inspection, console checks, or localhost UI debugging, use internal Codex Browser / Browser Use / in-app browser first; fall back to `firefox-devtools`, then `chrome-devtools`, then standalone Playwright.
- If the changes are primarily documentation, use docs.
- If review findings require GitHub Issues or ledger actions, use `intbridge:issues`.
- For deeper DB/Supabase guidance, use postgres or supabase skills.

## Reporting rules

- If no issues are found, say so explicitly.
- If issues are found, фиксируй их в GitHub Issues (без файловых отчётов).
- Each finding must include: severity, file/line, impact, and recommendation.
- Keep the summary brief; findings are primary.
