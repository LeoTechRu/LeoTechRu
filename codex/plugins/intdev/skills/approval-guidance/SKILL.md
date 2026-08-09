---
name: approval-guidance
description: Сохраняй отдельные effect-specific approvals для writes, publication, privileged runtime и destructive действий.
---

# Approval guidance

Разделяй identity, capability и approval: аутентификация подтверждает субъекта, capability — техническую возможность adapter, approval — один ограниченный эффект.

Перед consequential action зафиксируй target, точный эффект и arguments/digest, риск, ожидаемый результат, verification, rollback и срок действия. Используй native approval выбранного adapter. Не переноси confirmation между изменившимися arguments, targets, channels или истёкшим контекстом.

Work item, план, review, привилегированная сессия и прежнее разрешение не дают authority для другого outward, destructive или production effect. Если policy или нужный approval-механизм не настроены, подготовь bounded proposal и останови только этот effect.
