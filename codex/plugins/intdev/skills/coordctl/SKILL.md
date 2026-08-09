---
name: coordctl
description: Координируй repository work через настроенный session/intent/lease adapter и pre-commit scope checks.
---

# Coordination routing

Перед нетривиальной tracked mutation найди coordination policy текущего workspace и выбери поддерживаемый adapter. Он должен уметь наблюдаемо фиксировать task session, file/region intents, leases, base revision и pre-commit scope result.

Прочитай status, active sessions/intents и scope; начни или переиспользуй точную task session, зарегистрируй минимальные intents и поддерживай heartbeat. Intent координирует, но не разрешает запись. Перед commit выполни whole-file scope check; останови mutation при реальном overlap, stale base, ambiguous caller или изменившемся base.

Cleanup и garbage collection потенциально destructive: сначала покажи exact preview и получи требуемое policy approval. Remote adapter должен принимать стабильный target identifier, а не произвольный host path. Release связывай с exact session.

Ошибка выбранного adapter блокирует coordination-dependent mutation через этот route, но не read-only работу. Другой отдельно настроенный adapter допустим только после повторной проверки policy, base и overlaps; shell сам по себе не заменяет требуемое coordination evidence.
