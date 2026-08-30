# Agent Plane

`agent_plane` is a public first-party runtime package for policy-aware tool dispatch and local agent-tool harnesses. Agent-specific adapters, including the Codex MCP package, are private plugins owned by `LeoTechPro/Plugins`.

It provides reusable dispatcher, policy, audit, and server modules without binding the core package to one agent UI.

## Public Surface

- `agent_plane.dispatcher`
- `agent_plane.policy`
- `agent_plane.audit`
- `agent_plane.server`
- `agent_plane.local_harness`

Agent-specific integrations should remain adapters around this package, not requirements inside it.

## Runtime State

Runtime state must be caller-configured and kept outside source control. Audit logs, temporary payloads, secrets, and local process state do not belong in tracked files.

## Local Use

```powershell
python -m agent_plane.local_harness --help
python -m agent_plane.server --host 127.0.0.1 --port 9192
```

## Tests

```powershell
python -m unittest discover -s D:\int\tools\agent_plane\tests
```
