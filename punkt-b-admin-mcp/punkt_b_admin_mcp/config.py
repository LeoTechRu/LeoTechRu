from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlsplit


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _safe_http_url(value: str, *, allow_loopback_http: bool = False) -> str:
    parsed = urlsplit(value)
    loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme != "https" and not (allow_loopback_http and parsed.scheme == "http" and loopback):
        raise ValueError("URL must use HTTPS, except loopback MCP resource URLs")
    if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("URL contains forbidden components")
    return value.rstrip("/")


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    contour: str
    supabase_url: str
    supabase_anon_key: str
    oauth_issuer: str
    resource_url: str
    required_audience: str
    auth_timeout_seconds: float

    @classmethod
    def load(cls) -> "Config":
        host = os.getenv("PUNKT_B_ADMIN_HOST", "127.0.0.1").strip()
        if host not in {"127.0.0.1", "::1"}:
            raise ValueError("PUNKT_B_ADMIN_HOST must be loopback")
        port = int(os.getenv("PUNKT_B_ADMIN_PORT", "17443"))
        if port != 17443:
            raise ValueError("PUNKT_B_ADMIN_PORT must match the approved port 17443")
        contour = os.getenv("PUNKT_B_ADMIN_CONTOUR", "dev").strip()
        if contour != "dev":
            raise ValueError("This package version is dev-only")
        anon_key = os.getenv("PUNKT_B_ADMIN_SUPABASE_ANON_KEY", "").strip()
        if not anon_key:
            raise ValueError("PUNKT_B_ADMIN_SUPABASE_ANON_KEY is required")
        resource_url = _safe_http_url(
            os.getenv("PUNKT_B_ADMIN_RESOURCE_URL", "http://127.0.0.1:17443/mcp"),
            allow_loopback_http=True,
        )
        required_audience = os.getenv("PUNKT_B_ADMIN_REQUIRED_AUDIENCE", resource_url).strip()
        if not required_audience:
            raise ValueError("PUNKT_B_ADMIN_REQUIRED_AUDIENCE is required")
        return cls(
            host=host,
            port=port,
            contour=contour,
            supabase_url=_safe_http_url(
                os.getenv("PUNKT_B_ADMIN_SUPABASE_URL", "https://api.intdata.pro")
            ),
            supabase_anon_key=anon_key,
            oauth_issuer=_safe_http_url(
                os.getenv("PUNKT_B_ADMIN_OAUTH_ISSUER", "https://api.intdata.pro/auth/v1")
            ),
            resource_url=resource_url,
            required_audience=required_audience,
            auth_timeout_seconds=float(os.getenv("PUNKT_B_ADMIN_AUTH_TIMEOUT_SECONDS", "8")),
        )

    def effect_enabled(self, service: str, risk: str) -> bool:
        key = f"PUNKT_B_ADMIN_EFFECT_{service}_{risk}".upper()
        return _bool_env(key, False)
