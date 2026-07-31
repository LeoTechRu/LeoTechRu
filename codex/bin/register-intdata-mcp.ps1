param([Parameter(ValueFromRemainingArguments = $true)][string[]]$RegistrationArgs)
$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = $env:INTDATA_MCP_PYTHON
if (-not $python) {
    if ($env:USERPROFILE) {
        $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
        if (Test-Path -LiteralPath $bundledPython -PathType Leaf) {
            $python = $bundledPython
        }
    }
}
if (-not $python) {
    $pythonCommand = Get-Command python.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pythonCommand) {
        $python = $pythonCommand.Source
    }
}
if (-not [System.IO.Path]::IsPathRooted($python) -or -not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'Set INTDATA_MCP_PYTHON to an existing absolute Python interpreter.'
}
$python = (Resolve-Path -LiteralPath $python).Path
& $python (Join-Path $scriptDir 'intdata_mcp_registration.py') --python $python @RegistrationArgs
exit $LASTEXITCODE
