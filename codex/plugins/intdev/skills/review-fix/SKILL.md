---
name: review-fix
description: Перепроверяй imported findings по текущему ground truth и исправляй только подтверждённое в approved scope.
---

# Review fix

Каждый finding независимо классифицируй как `confirmed`, `partially confirmed`, `not confirmed`, `outdated` или `architecture opinion`. Mutate только подтверждённую часть и только при authority текущего запроса. Сохраняй unrelated/foreign dirty state.

После исправления выполни focused verification, перечитай source/diff и повтори исходный reproduction/falsifier. Сообщи resolved/partial/rejected findings, exact range, evidence и unverified boundaries.

Не превращай архитектурные предпочтения в fixes и не расширяй работу до cleanup, publication или production. Specification, work-item, coordination и approval gates остаются отдельными и берутся из configured policy.
