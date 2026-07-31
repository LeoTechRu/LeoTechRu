from __future__ import annotations

import asyncio
import base64
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from mcp.server.auth.provider import AccessToken

from punkt_b_admin_mcp.config import Config


class SupabaseAdminTokenVerifier:
    """Verify the caller and current users:manage authority without service role."""

    def __init__(self, config: Config) -> None:
        self.config = config

    @staticmethod
    def _claims(token: str) -> dict[str, Any]:
        try:
            segment = token.split(".")[1]
            padding = "=" * (-len(segment) % 4)
            return json.loads(base64.urlsafe_b64decode(segment + padding))
        except (IndexError, ValueError, json.JSONDecodeError):
            return {}

    def _audience_matches(self, claims: dict[str, Any]) -> bool:
        audience = claims.get("aud")
        if isinstance(audience, str):
            return audience == self.config.required_audience
        if isinstance(audience, list):
            return self.config.required_audience in audience
        return False

    def _request_json(self, path: str, token: str, body: bytes | None = None) -> Any:
        headers = {
            "Authorization": f"Bearer {token}",
            "apikey": self.config.supabase_anon_key,
            "Accept": "application/json",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self.config.supabase_url}{path}",
            data=body,
            headers=headers,
            method="POST" if body is not None else "GET",
        )
        try:
            with urlopen(request, timeout=self.config.auth_timeout_seconds) as response:
                if response.status < 200 or response.status >= 300:
                    return None
                return json.loads(response.read(65536))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            return None

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token or len(token) > 16384:
            return None
        claims = self._claims(token)
        oauth_client_id = claims.get("client_id")
        if not isinstance(oauth_client_id, str) or not oauth_client_id.strip():
            return None
        if not self._audience_matches(claims):
            return None
        user = await asyncio.to_thread(self._request_json, "/auth/v1/user", token)
        if not isinstance(user, dict) or not isinstance(user.get("id"), str):
            return None
        allowed = await asyncio.to_thread(
            self._request_json,
            "/rest/v1/rpc/current_user_has_perm",
            token,
            json.dumps({"p_perm_code": "users:manage"}).encode(),
        )
        if allowed is not True:
            return None
        scopes = claims.get("scope", "")
        scope_list = scopes.split() if isinstance(scopes, str) else []
        # users:manage is an effective backend permission, not a claim trusted
        # from the token. Expose it to FastMCP only after the live RPC above has
        # confirmed the current actor still has that permission.
        effective_scopes = list(dict.fromkeys([*scope_list, "users:manage"]))
        return AccessToken(
            token=token,
            # FastMCP uses AccessToken.client_id as the audit/rate-limit actor.
            # Record the freshly verified user rather than an untrusted email or
            # a local allowlist; the OAuth client_id is still required above.
            client_id=user["id"],
            scopes=effective_scopes,
            expires_at=claims.get("exp") if isinstance(claims.get("exp"), int) else None,
            resource=self.config.resource_url,
        )
