@echo off
setlocal
set "UNISENDER_MCP_ROOT=%~dp0"
set "PYTHONPATH=%UNISENDER_MCP_ROOT%..\.runtime\getcourse-mcp\.deps;%UNISENDER_MCP_ROOT%;%PYTHONPATH%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%UNISENDER_MCP_ROOT%..\.runtime\credentials\unisender-api-credential.ps1" -Exec python -m unisender_mcp.server %*
