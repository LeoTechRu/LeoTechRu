# Punkt B Admin MCP

Private Streamable HTTP MCP gateway for issue
[#780](https://github.com/LeoTechPro/int/issues/780). It binds only
`127.0.0.1:17443`, validates a caller token against Supabase and rechecks the
current effective `users:manage` permission on every MCP request.

The committed registry is the complete tool allowlist. Startup fails on unknown
risk classes, duplicate names, missing schemas/annotations/permission, or a
write-capable entry without confirmation and idempotency policy. External effect
flags default to disabled. If a dev effect is ever explicitly enabled, a
process-local duplicate-key guard rejects a second use before the adapter runs;
a production contour would additionally require a durable shared receipt store.

## Required runtime configuration

- `PUNKT_B_ADMIN_SUPABASE_URL` — canonical API origin;
- `PUNKT_B_ADMIN_SUPABASE_ANON_KEY` — protected runtime secret pointer value;
- `PUNKT_B_ADMIN_OAUTH_ISSUER` — authorization server issuer;
- `PUNKT_B_ADMIN_RESOURCE_URL` — admin MCP resource identifier;
- `PUNKT_B_ADMIN_REQUIRED_AUDIENCE` — exact admin-only JWT `aud`; defaults to
  the resource identifier.

The OAuth issuer must mint a token with a non-empty OAuth `client_id` and the
exact admin audience. With Supabase Auth, the audience is set by a Custom Access
Token Hook. The gateway then revalidates the user and calls
`current_user_has_perm('users:manage')` with the caller token on every request.
A normal specialist token with the default `authenticated` audience is rejected
before any provider request.

No secret belongs in this repository or the plugin artifact. Service adapters
are enabled only when their canonical service libraries and protected runtime
configuration are present. Missing adapters return a bounded
`ADAPTER_NOT_CONFIGURED` response rather than falling back to a shell command or
arbitrary URL.

The gateway currently wires all 12 read/compute namespaces. amoCRM, Umnico,
GetCourse, Bitrix24 and Vakas reuse their canonical Python service packages;
Tilda uses its fixed official API host; LK uses the caller token; Telegram uses
the fixed `tdl-work` executable without a shell; accounting mail opens the fixed
mailbox read-only; project files search metadata only under the fixed VFS root.
Reporting and sales analytics are bounded deterministic computations. Mail
bodies, attachments and binary project files are never returned.

The committed input schema is also the exact schema advertised by `tools/list`
and is revalidated immediately before dispatch. Registry `output_schema`
describes the adapter data field; the gateway wraps it in the stable
`ok/contour/service/operation/data/pagination/receipt` envelope.

## Run

```bash
python -m punkt_b_admin_mcp
```

The MCP endpoint is `http://127.0.0.1:17443/mcp`. Production deployment is out
of scope for this package version.
