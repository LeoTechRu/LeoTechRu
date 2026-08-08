---
name: issues
description: Применяй каноническую GitHub Issue discipline и risk-based review routing для tracked intData work.
---

# GitHub Issues and review workflow

Канонические требования: `/int/openspec/specs/process/spec.md`.

Для нетривиальной tracked work используй один reachable `LeoTechPro/int` Issue через authenticated `gh` или наблюдаемый GitHub adapter. Issue хранит scope/status/evidence; Goal — resumable execution; OpenSpec — durable `delta|full` requirements; coordctl — локальную coordination provenance. Cache и remembered state не являются authority.

Зафиксируй `Specification level: none|delta|full`; highest trigger wins. Перед mutation сверяй ownership, protected dirty state, reachable related tasks и coordctl intents. Не публикуй prompts, reasoning, transcripts, raw outputs или secrets.

Открытый Issue имеет ровно один `status:*`; completed закрывается с `completed`, cancellation — `not_planned`. Read-only/diagnostic/review не разрешают GitHub writes. Live lookup обязателен для issue-gated/outward effects; auth/API/status ambiguity блокирует только зависимый effect.

Issue, review и local commit не разрешают push, deployment, DB apply, production, destructive или shared-history mutation. В closeout укажи URL/status, revisions, OpenSpec, checks, runtime/publication boundaries, rollback, foreign dirt и residual risks.
