---
name: delivery-acceptance
description: Формируй evidence-based triage, acceptance, release-readiness и handoff verdict без выдачи отсутствующих approvals.
---

# Delivery acceptance

Выбери режим `triage`, `acceptance`, `release-readiness` или `handoff` и независимо оцени:

1. contract: configured work item, specification и recorded decisions;
2. source: exact revision и protected dirty boundaries;
3. verification: tests, compatibility, security review;
4. publication;
5. deploy/apply;
6. runtime;
7. native/browser acceptance;
8. rollback/safe stop.

Верни `PASS`, `BLOCK` или `PASS WITH UNVERIFIED BOUNDARIES`, затем evidence, blockers, residual risks и exact next action. Не выводи publication из local commit, deploy из publication или user acceptance из server smoke.

Навык read-only: он не меняет work tracker/runtime и не разрешает commit, push, deploy, data apply, cleanup или destructive action.
