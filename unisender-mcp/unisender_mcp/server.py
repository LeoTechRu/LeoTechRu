from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

SAFE_READ_METHODS = {"getLists", "getTotalContactsCount", "getFields", "getTags"}
mcp = FastMCP("Punkt B Unisender MCP")
_client: httpx.AsyncClient | None = None


def _api_key() -> str:
    key = os.environ.get("UNISENDER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("UNISENDER_API_KEY is not configured")
    return key


async def _call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    global _client
    try:
        key = _api_key()
        if _client is None:
            _client = httpx.AsyncClient(base_url="https://api.unisender.com/ru/api", timeout=httpx.Timeout(20, connect=10))
        response = await _client.post(f"/{method}", data={"format": "json", "api_key": key, **(params or {})})
        response.raise_for_status()
        data = response.json()
        if data.get("error"):
            return {"ok": False, "error": str(data["error"])[:300], "status_code": response.status_code}
        return {"ok": True, "data": data.get("result")}
    except (RuntimeError, httpx.HTTPError, ValueError):
        return {"ok": False, "error": "Unisender API request failed"}


@mcp.tool()
async def unisender_health() -> dict:
    """Show Unisender configuration without exposing the Punkt B API key."""
    try:
        _api_key()
        return {"ok": True, "api_key_configured": True, "api_base_url": "https://api.unisender.com/ru/api"}
    except RuntimeError:
        return {"ok": False, "api_key_configured": False}


@mcp.tool()
async def unisender_lists_get() -> dict:
    """List Unisender mailing lists (read-only)."""
    return await _call("getLists")


@mcp.tool()
async def unisender_contact_total() -> dict:
    """Return total Unisender contact count (read-only)."""
    return await _call("getTotalContactsCount")


@mcp.tool()
async def unisender_api_read(method: str, params: dict | None = None) -> dict:
    """Call one allowlisted read-only Unisender API method."""
    if method not in SAFE_READ_METHODS:
        return {"ok": False, "error": "Method is not allowlisted", "allowed": sorted(SAFE_READ_METHODS)}
    return await _call(method, params)


@mcp.tool()
async def unisender_email_send(email: str, subject: str, body: str, sender_name: str, sender_email: str, confirm_send: bool = False) -> dict:
    """Send one email; requires explicit confirm_send=True."""
    if confirm_send is not True:
        return {"ok": False, "error": "confirm_send=True is required before sending email"}
    payload = {"email": email, "subject": subject, "body": body, "sender_name": sender_name, "sender_email": sender_email}
    if any(not str(value).strip() for value in payload.values()):
        return {"ok": False, "error": "email, subject, body, sender_name, and sender_email are required"}
    return await _call("sendEmail", payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Punkt B Unisender MCP")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        print(json.dumps(asyncio.run(unisender_health()), ensure_ascii=False))
    else:
        asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main()
