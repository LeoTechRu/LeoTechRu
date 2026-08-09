---
name: issues
description: Применяй настроенную issue discipline и risk-based review routing для tracked work.
---

# Issues and review workflow

Сначала найди policy текущего workspace: provider, repository/project, status model, specification levels, review triggers и допустимые write operations. Не подставляй значения по умолчанию, если target или policy неоднозначны.

Для нетривиальной tracked work свяжи изменения с одним reachable work item через настроенный provider adapter. Work item хранит scope/status/evidence; durable specification и coordination state принадлежат их настроенным системам. Cache и remembered state не являются authority.

Зафиксируй требуемый policy-specific specification level. Перед mutation сверяй ownership, protected dirty state, related work и active coordination intents. Не публикуй prompts, reasoning, transcripts, raw outputs или secrets.

Валидируй status и close semantics по provider policy. Read-only, diagnostic и review запросы не разрешают tracker writes. Live lookup обязателен для issue-gated/outward effects; auth, API или status ambiguity блокирует только зависимый effect.

Work item, review и local commit не разрешают push, deployment, data apply, production, destructive или shared-history mutation. В closeout укажи stable item reference/status, revisions, specification, checks, runtime/publication boundaries, rollback, foreign dirt и residual risks.
