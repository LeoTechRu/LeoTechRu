import json
import inspect
import logging
import time
import uuid
from typing import Any

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from starlette.responses import JSONResponse

from punkt_b_admin_mcp.adapters import AdapterDispatcher
from punkt_b_admin_mcp.auth import SupabaseAdminTokenVerifier
from punkt_b_admin_mcp.config import Config
from punkt_b_admin_mcp.registry import Registry, ToolEntry, load_registry
from punkt_b_admin_mcp.security import GatewayError, RateLimiter


logger = logging.getLogger("punkt_b_admin_mcp.audit")


def _ok(registry: Registry, entry: ToolEntry, data: Any, request_id: str) -> dict[str, Any]:
    return {
        "ok": True,
        "contour": registry.contour,
        "service": entry.service,
        "operation": entry.operation,
        "data": data,
        "pagination": None,
        "receipt": {"request_id": request_id, "registry_hash": registry.sha256},
    }


def _error(registry: Registry, entry: ToolEntry, error: GatewayError, request_id: str) -> dict[str, Any]:
    return {
        "ok": False,
        "contour": registry.contour,
        "service": entry.service,
        "code": error.code,
        "retryable": error.retryable,
        "request_id": request_id,
    }


def create_server(config: Config | None = None, registry: Registry | None = None) -> FastMCP:
    config = config or Config.load()
    registry = registry or load_registry()
    verifier = SupabaseAdminTokenVerifier(config)
    mcp = FastMCP(
        "Punkt B Admin Gateway",
        instructions="Private dev gateway. Every call requires current users:manage authority.",
        token_verifier=verifier,
        host=config.host,
        port=config.port,
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        auth=AuthSettings(
            issuer_url=config.oauth_issuer,
            resource_server_url=config.resource_url,
            required_scopes=["users:manage"],
        ),
    )
    dispatcher = AdapterDispatcher(config)
    limiter = RateLimiter()

    async def protected_resource_metadata(request):
        return JSONResponse({
            "resource": config.resource_url,
            "authorization_servers": [config.oauth_issuer],
            "scopes_supported": ["users:manage"],
            "bearer_methods_supported": ["header"],
        })

    # mcp 1.12 advertises the resource-relative metadata URL in the challenge
    # but only mounts the root form. Publish both RFC 9728 forms explicitly.
    mcp.custom_route("/.well-known/oauth-protected-resource/mcp", ["GET"])(protected_resource_metadata)
    mcp.custom_route("/mcp/.well-known/oauth-protected-resource", ["GET"])(protected_resource_metadata)

    def make_invoke(entry: ToolEntry):
        async def invoke(**payload: Any) -> dict[str, Any]:
            request_id = str(uuid.uuid4())
            started = time.monotonic()
            access = get_access_token()
            actor = access.client_id if access is not None else "unauthenticated"
            result_code = "OK"
            try:
                limiter.check(actor, entry.tool_name, entry.rate_limit_per_minute)
                data = await dispatcher.execute(entry, payload, caller_token=access.token if access is not None else "")
                return _ok(registry, entry, data, request_id)
            except GatewayError as exc:
                result_code = exc.code
                return _error(registry, entry, exc, request_id)
            except Exception:
                result_code = "INTERNAL_ERROR"
                logger.exception("adapter failure tool=%s request_id=%s", entry.tool_name, request_id)
                return _error(registry, entry, GatewayError("INTERNAL_ERROR", "Internal gateway error"), request_id)
            finally:
                logger.info(json.dumps({
                    "actor": actor,
                    "tool": entry.tool_name,
                    "contour": registry.contour,
                    "duration_ms": round((time.monotonic() - started) * 1000),
                    "result_code": result_code,
                    "request_id": request_id,
                }, sort_keys=True))

        parameters = []
        properties = entry.input_schema.get("properties", {})
        required = set(entry.input_schema.get("required", []))
        for name in properties:
            parameters.append(inspect.Parameter(
                name,
                inspect.Parameter.KEYWORD_ONLY,
                default=inspect.Parameter.empty if name in required else None,
                annotation=Any,
            ))
        invoke.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
            parameters,
            return_annotation=dict[str, Any],
        )
        return invoke

    for entry in registry.tools:
        invoke = make_invoke(entry)
        invoke.__name__ = entry.tool_name
        annotations = ToolAnnotations(**entry.annotations)
        mcp.tool(
            name=entry.tool_name,
            description=f"{entry.service}: {entry.operation} ({entry.risk})",
            annotations=annotations,
            structured_output=True,
        )(invoke)
        # FastMCP derives a structural schema from the Python signature. The
        # committed capability registry remains authoritative for bounds and
        # additionalProperties, so advertise that exact schema as well as
        # validating it again immediately before dispatch.
        registered = mcp._tool_manager.get_tool(entry.tool_name)
        if registered is None:
            raise RuntimeError(f"Failed to register tool: {entry.tool_name}")
        registered.parameters = entry.input_schema

    return mcp


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    server = create_server()
    server.run(transport="streamable-http")
