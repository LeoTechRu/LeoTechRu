[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$toolsDir = (Resolve-Path $PSScriptRoot).Path
$repoRoot = (Resolve-Path (Join-Path $toolsDir "../..")).Path
$openSpecDir = Join-Path $toolsDir "openspec"

Push-Location $openSpecDir
try {
    npm ci
} finally {
    Pop-Location
}

Write-Output "Готово. Используйте локальную команду:"
Write-Output "  $repoRoot/codex/bin/openspec --version"
Write-Output "coordctl теперь поставляется intData Node: /int/node/coordctl"
