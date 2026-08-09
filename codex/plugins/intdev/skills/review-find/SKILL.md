---
name: review-find
description: Выполняй evidence-backed hostile review плана, diff или runtime claim без mutation target.
---

# Review find

Считай результат и claims недоверенными. Зафиксируй exact files/range/runtime/plan, прочитай configured instructions, work item и specification, проверь ground truth и попытайся опровергнуть correctness, compatibility, security и acceptance claims. Используй adverse inputs, changed-base, trust-boundary и negative activation cases.

Для confirmed finding укажи severity, category, exact range, reproduction/proof, impact и smallest safe remediation. Не выдавай preference или speculative hardening за defect. При отсутствии findings назови inspected range и untested boundaries.

Review read-only: не исправляй, не публикуй, не меняй work-item status и не считай source review runtime acceptance.
