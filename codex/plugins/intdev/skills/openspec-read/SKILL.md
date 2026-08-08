---
name: openspec-read
description: Находи, читай и валидируй OpenSpec source of truth без lifecycle mutations.
---

# OpenSpec read routing

Используй для list, show, status, instructions и validation существующего package.

1. Определи repository root и ближайшие instructions.
2. Подтверди наличие OpenSpec source of truth.
3. Выбери наименее привилегированный совместимый read route: dedicated tool, repository adapter или отдельно разрешённый native shell.
4. Сообщи exact package/spec, validation result и drift.

Ошибка одного adapter блокирует только его route и не запрещает другой независимо разрешённый read route. Не создавай, не редактируй, не архивируй и не меняй checkboxes этим навыком. Если источник нельзя прочитать ни одним разрешённым маршрутом, отметь boundary как unverified.
