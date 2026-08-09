# int-tools remote MCP app v1

## Purpose

Expose a curated, internal, tool-only ChatGPT Apps MCP surface for intData tooling. This is not a mirror of local Codex plugins, `mcp-intdata-cli.py`, or the neutral `agent_plane_call` facade.

## Architecture

- Archetype: `tool-only`.
- Source contour: `tools/chatgpt-apps/int-tools-mcp/`.
- Endpoint: stable HTTP/HTTPS MCP endpoint at `/mcp`.
- Local default: `http://127.0.0.1:9193/mcp`.
- Production target: stable public HTTPS `/mcp`.
- UI/widget: none in v1.
- Auth: bearer token from runtime secret store via `INT_TOOLS_MCP_BEARER_TOKEN`.
- Optional owner default: `INT_TOOLS_MCP_OWNER_ID`.
- Logging: request id, actor, tool name, latency, result class, and guard decision when access logging is enabled.

The existing local Codex MCP layer remains in `tools/codex/plugins/*` and `tools/codex/bin/mcp-intdata-cli.py`. The neutral Agent Plane remains internal under `tools/agent_plane/*`.

## V1 tool surface

All v1 tools are read-only and must use `annotations.readOnlyHint=true`.

- `search`: search intData knowledge, memory, or context.
- `fetch`: fetch one safe item id returned by `search`.
- `routing_validate`: validate high-risk intData tooling routing registry.

Do not expose in v1:

- generic `agent_plane_call`;
- raw profile tools from `mcp-intdata-cli.py`;
- OpenSpec tools, until OpenSpec has a separate MCP surface or an explicit compatibility exception;
- mutating IntBrain writes;
- coordctl tools; coordctl is owned by intData Node, not intData-tools remote MCP;
- retired coordination tools;
- Multica operations;
- DB apply/migrations;
- publish or sync-gate wrappers;
- browser/profile launch;
- vault non-dry-run.

## Result contract

Each tool returns:

- `structuredContent`: stable machine-readable result;
- `content`: short human-readable summary;
- `_meta`: only for future widget-only data, not used in v1.

The server must not return JSON only as text in `content`. Internal profile names are not part of the public API.

## Local development

```powershell
cd D:\int\tools\chatgpt-apps\int-tools-mcp
python -m int_tools_mcp.server --host 127.0.0.1 --port 9193
```

Optional auth:

```powershell
$env:INT_TOOLS_MCP_BEARER_TOKEN = "<runtime-secret>"
$env:INT_TOOLS_MCP_OWNER_ID = "1"
python -m int_tools_mcp.server --host 127.0.0.1 --port 9193
```

ChatGPT Developer Mode check:

1. Start the local server.
2. Expose it with an HTTPS tunnel, for example `ngrok http 9193`.
3. Register the app in ChatGPT Developer Mode with the tunneled `/mcp` URL.
4. Refresh the app after changing tool descriptors.
5. Verify `search`, `fetch`, and `routing_validate`.

## Production gate

Production enablement requires:

- stable HTTPS endpoint;
- bearer auth backed by runtime secret storage;
- request logging and latency/error visibility;
- rate limiting;
- smoke tests for `tools/list`, `search`, `fetch`, auth failure, and `routing_validate`;
- no direct writes to `C:\Users\intData\.codex`.

Repo scripts must not install, patch, mirror, or rewrite Codex home. Codex home changes may only happen through documented native Codex plugin/config flows or explicit manual owner action.

## References

- OpenAI Apps SDK MCP server docs: `https://developers.openai.com/apps-sdk/build/mcp-server`
- OpenAI Apps SDK tool planning docs: `https://developers.openai.com/apps-sdk/plan/tools`
- OpenAI Apps SDK reference: `https://developers.openai.com/apps-sdk/reference`
