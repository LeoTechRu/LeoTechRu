---
name: openspec-mutation
description: Маршрутизируй явно разрешённое создание и изменение OpenSpec через настроенные work-item и level-aware gates.
---

# OpenSpec mutation routing

Используй только когда запрос явно разрешает specification mutation. До записи нужны настроенные repository/work-item references, policy-specific level, approved package path или разрешение создать его, governing instructions, dirty-state inventory и отдельно разрешённый write route.

Обновляй текущий active package; не переписывай historical packages для сокрытия drift. Requirements принадлежат specification repository, execution status — настроенному work tracker, coordination — настроенному coordination adapter. После изменений выполни strict validation и repository profile/policy check.

Ошибка одного mutation adapter блокирует только его route. Другой separately authorized repository write route допустим, если заново проходит те же work-item/specification/dirty/coordination/approval gates. Навык не выдаёт authority на code mutation, publication, deployment, data apply или archive.
