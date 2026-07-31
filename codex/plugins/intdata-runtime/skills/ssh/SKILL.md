---
name: ssh
description: Runtime SSH routes and bounded native OpenSSH execution with a resolver-first fallback policy.
---

# Runtime SSH routes

Use `ssh_resolve` as preferred read-only route discovery. It is an optimizer, not a mandatory transport dependency.

## Resolver-first fallback

1. Try `ssh_resolve` when it is observable.
2. If the tool/process is missing or unavailable, native `ssh` MAY be used for the exact explicit alias or `user@host` supplied by the owner.
3. Never infer a user, hostname or production target.
4. A policy/config/ambiguity denial is authoritative: stop instead of falling back.
5. Native fallback keeps batch authentication, strict host-key verification, disabled password/keyboard-interactive authentication, and bounded timeout/output.
6. Route discovery never authorizes a mutating remote command.

## Tool cards

### ssh_resolve

- Когда: нужно read-only определить preferred SSH route.
- Required inputs: `host`.
- Optional/schema inputs: `cwd`, `timeout_sec`, `mode`, `json`, `destination_only`.
- Режим: read-only.
- Approval / issue requirements: не требуются для route discovery.
- Не использовать когда: target не задан явно либо resolver вернул policy/config/ambiguity denial.
- Пример вызова: `{"name":"ssh_resolve","arguments":{"host":"dev-agents","json":true}}`.
- Fallback/blocker: missing/unavailable resolver допускает native SSH только к exact owner-supplied destination; policy denial блокирует.

### ssh_execute

- Когда: нужно выполнить bounded remote command через system OpenSSH.
- Required inputs: `host`, structured `argv`, `execution_mode`.
- Optional/schema inputs: `remote_cwd`, `mode`, `timeout_sec`, `max_output_bytes`, `confirm_mutation`, `issue_context`.
- Режим: read-only by default; mutation only when explicitly declared.
- Approval / issue requirements: mutation requires `confirm_mutation=true`, `issue_context=#N`, owner approval and all production/destructive gates.
- Не использовать когда: command semantics are unknown, destination is implicit/ambiguous, host key fails, interactive auth is required, or approval is missing.
- Пример вызова: `{"name":"ssh_execute","arguments":{"host":"dev-agents","argv":["uname","-a"],"execution_mode":"read_only"}}`.
- Fallback/blocker: the adapter never receives keys/passphrases and never invokes a local shell; timeout, host-key mismatch and interactive auth fail closed.
