. (Join-Path $PSScriptRoot 'dev-common.ps1')

$modeState = Get-DevMode
$mode = if ($null -eq $modeState) { 'local' } else { [string]$modeState.mode }
$apiTarget = if ($null -eq $modeState) { 'http://127.0.0.1:8000' } else { [string]$modeState.apiTarget }
$tunnelRunning = $null -ne (Get-SshTunnelProcess)
$postgresConnected = if ($mode -eq 'local') { Test-PostgreSqlConnection } else { $false }
$backendRunning = if ($mode -eq 'local') { Test-BackendHealth } else { Test-RemoteBackendHealth $apiTarget }
$frontendRunning = Test-FrontendReal
$electronRunning = Test-ElectronRunning

Write-DevStatus 'SSH Tunnel' $tunnelRunning 'RUNNING' $(if ($mode -eq 'remote') { 'NOT REQUIRED' } else { 'STOPPED' })
Write-DevStatus 'PostgreSQL' $postgresConnected 'CONNECTED' $(if ($mode -eq 'remote') { 'VIA VPS BACKEND' } else { 'DISCONNECTED' })
Write-DevStatus 'Backend' $backendRunning
Write-DevStatus 'Frontend' $frontendRunning
Write-DevStatus 'Electron' $electronRunning
Write-Host ('{0,-14} {1}' -f 'API Mode', 'real')
Write-Host ('{0,-14} {1}' -f 'Dev Mode', $mode)
Write-Host ('{0,-14} {1}' -f 'API Target', $apiTarget)
