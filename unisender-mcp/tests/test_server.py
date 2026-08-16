import pytest

from unisender_mcp.server import unisender_api_read, unisender_email_send


@pytest.mark.asyncio
async def test_rejects_non_allowlisted_read_method():
    result = await unisender_api_read("deleteList")
    assert result["ok"] is False


@pytest.mark.asyncio
async def test_rejects_send_without_confirmation():
    result = await unisender_email_send("a@example.com", "subject", "body", "Punkt B", "mail@example.com")
    assert result["ok"] is False
    assert "confirm_send" in result["error"]
