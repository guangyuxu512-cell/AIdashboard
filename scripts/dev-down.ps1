. (Join-Path $PSScriptRoot 'dev-common.ps1')

foreach ($name in @('electron', 'frontend', 'backend', 'ssh')) {
    if (Stop-ManagedProcess $name) {
        Write-Host "Stopped managed $name process tree."
    }
    else {
        Write-Host "Skipped $name (not managed by this tooling)."
    }
}

Remove-DevMode

if (Test-Path -LiteralPath (Get-DevRuntimeDirectory)) {
    $remainingState = @(Get-ChildItem -LiteralPath (Get-DevRuntimeDirectory) -Filter '*.json' -ErrorAction SilentlyContinue)
    if ($remainingState.Count -eq 0) {
        Remove-Item -LiteralPath (Get-DevRuntimeDirectory) -Recurse -Force
    }
}

& (Join-Path $PSScriptRoot 'dev-status.ps1')
