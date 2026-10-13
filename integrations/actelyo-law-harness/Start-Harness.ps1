param(
    [ValidateSet('Doctor','Serve','Mcp','Test')][string]$Action = 'Doctor',
    [string]$Config = 'config.toml',
    [int]$Port = 8765
)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $pythonCommand = Get-Command python -ErrorAction Stop
    if ($Action -eq 'Test') {
        & $pythonCommand.Source -m unittest discover -s tests -v
    } elseif ($Action -eq 'Serve') {
        & $pythonCommand.Source -m law_harness --config $Config serve --port $Port
    } elseif ($Action -eq 'Mcp') {
        & $pythonCommand.Source -m law_harness --config $Config mcp
    } else {
        & $pythonCommand.Source -m law_harness --config $Config doctor --probe-model
    }
    $harnessExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $harnessExitCode
