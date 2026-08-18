. (Join-Path $PSScriptRoot 'dev-common.ps1')

$tunnelRunning = $null -ne (Get-SshTunnelProcess)
$postgresConnected = Test-PostgreSqlConnection
$backendRunning = Test-BackendHealth
$frontendRunning = Test-FrontendReal
$electronRunning = Test-ElectronRunning

Write-DevStatus 'SSH Tunnel' $tunnelRunning
Write-DevStatus 'PostgreSQL' $postgresConnected 'CONNECTED' 'DISCONNECTED'
Write-DevStatus 'Backend' $backendRunning
Write-DevStatus 'Frontend' $frontendRunning
Write-DevStatus 'Electron' $electronRunning
Write-Host ('{0,-14} {1}' -f 'API Mode', 'real')
