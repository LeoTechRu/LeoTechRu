---
name: openspec-mutation
description: Маршрутизируй явно разрешённое создание и изменение OpenSpec через issue-bound и level-aware gates.
---

# OpenSpec mutation routing

Используй только когда запрос явно разрешает specification mutation. До записи нужны canonical Issue/repository, level `delta|full`, approved package path или разрешение создать его, governing instructions, dirty-state inventory и отдельно разрешённый write route.

Обновляй текущий active package; не переписывай historical packages для сокрытия drift. Requirements принадлежат OpenSpec, execution status — Issue/Goal, coordination — coordctl. После изменений выполни strict validation и repo profile/policy check.

Ошибка одного mutation adapter блокирует только его route. Другой separately authorized repository write route допустим, если заново проходит те же Issue/OpenSpec/dirty/coordination/approval gates. Навык не выдаёт authority на code mutation, publication, deployment, DB apply или archive.
