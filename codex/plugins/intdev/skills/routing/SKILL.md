---
name: routing
description: Разрешай logical technical intent в canonical repository, service или adapter без обхода ownership и blocked paths.
---

# Canonical routing

Определи logical intent, target и effect. Прочитай current repository map/routing registry доступным read route, выбери owning repository/service и least-privileged compatible adapter. Перед tracked mutation проверь protected dirt, blocked paths и coordination. Сохраняй source, publication, runtime, browser и production как отдельные contours.

Ошибка выбранного registry/adapter блокирует только этот route. Можно использовать другой независимо разрешённый источник или adapter, включая native shell/SSH, только после повторной проверки всех применимых `Issue`, `OpenSpec`, ownership, protected-dirt, coordctl, safety, approval, destructive и outward gates этого маршрута. Отказ одного adapter не отменяет, не заменяет и не ослабляет ни один из этих gates, не даёт authority и не создаёт глобальный запрет. Если ownership всё ещё не доказан, отметь route uncertain и запроси target вместо догадки.
