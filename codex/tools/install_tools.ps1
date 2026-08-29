[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Output "OpenSpec управляется глобально через @fission-ai/openspec: openspec --version"
Write-Output "Coordination предоставляет intData Node только через установленную команду: intnode coord --help"
