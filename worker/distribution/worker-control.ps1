param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Configure', 'Start', 'Stop', 'Status')]
    [string]$Action,
    [string]$ImportConfigPath,
    [switch]$StartAfterConfigure,
    [switch]$AllowInsecureLoopback
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Security

$packageRoot = $PSScriptRoot
$workerExecutable = Join-Path $packageRoot 'ecommerce-worker\ecommerce-worker.exe'
$dataRoot = if ($env:ECOMMERCE_WORKER_DATA_ROOT) {
    [System.IO.Path]::GetFullPath($env:ECOMMERCE_WORKER_DATA_ROOT)
}
else {
    Join-Path $env:LOCALAPPDATA 'EcommerceAIWorker'
}
$configPath = Join-Path $dataRoot 'config.json'
$statePath = Join-Path $dataRoot 'worker-state.json'
$runtimeRoot = Join-Path $dataRoot 'runtime'
$logRoot = Join-Path $dataRoot 'logs'

function Protect-DataDirectory {
    New-Item -ItemType Directory -Path $dataRoot -Force | Out-Null
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    & icacls.exe $dataRoot /inheritance:r /grant:r "${identity}:(OI)(CI)F" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to restrict the Worker data directory to the current user.'
    }
}

function Protect-Token([string]$Token) {
    $plainBytes = [System.Text.Encoding]::UTF8.GetBytes($Token)
    try {
        $protectedBytes = [System.Security.Cryptography.ProtectedData]::Protect(
            $plainBytes,
            $null,
            [System.Security.Cryptography.DataProtectionScope]::CurrentUser
        )
        return [Convert]::ToBase64String($protectedBytes)
    }
    finally {
        [Array]::Clear($plainBytes, 0, $plainBytes.Length)
    }
}

function Unprotect-Token([string]$ProtectedToken) {
    $protectedBytes = [Convert]::FromBase64String($ProtectedToken)
    $plainBytes = [System.Security.Cryptography.ProtectedData]::Unprotect(
        $protectedBytes,
        $null,
        [System.Security.Cryptography.DataProtectionScope]::CurrentUser
    )
    try {
        return [System.Text.Encoding]::UTF8.GetString($plainBytes)
    }
    finally {
        [Array]::Clear($plainBytes, 0, $plainBytes.Length)
    }
}

function Convert-SecureStringToPlainText([Security.SecureString]$Value) {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Assert-ServerUrl([string]$ServerUrl) {
    $uri = $null
    if (-not [uri]::TryCreate($ServerUrl, [UriKind]::Absolute, [ref]$uri)) {
        throw 'Server URL must be an absolute URL.'
    }
    if ($uri.Scheme -eq 'https') {
        return $uri.AbsoluteUri.TrimEnd('/')
    }
    if ($AllowInsecureLoopback -and $uri.Scheme -eq 'http' -and $uri.IsLoopback) {
        Write-Warning 'Using loopback HTTP only for an explicit local/SSH-tunnel test.'
        return $uri.AbsoluteUri.TrimEnd('/')
    }
    throw 'Worker Server URL must use HTTPS. Public plaintext HTTP is refused.'
}

function Get-WorkerConfig {
    if (-not (Test-Path -LiteralPath $configPath)) {
        throw 'Worker is not configured. Run 首次配置并启动.cmd first.'
    }
    return Get-Content -Raw -Encoding UTF8 -LiteralPath $configPath | ConvertFrom-Json
}

function Get-RunningWorkerProcess {
    if (-not (Test-Path -LiteralPath $statePath)) {
        return $null
    }
    try {
        $state = Get-Content -Raw -Encoding UTF8 -LiteralPath $statePath | ConvertFrom-Json
        $process = Get-Process -Id ([int]$state.pid) -ErrorAction Stop
        $expectedStart = ([datetime]$state.started_at_utc).ToUniversalTime()
        $actualStart = $process.StartTime.ToUniversalTime()
        $expectedPath = [System.IO.Path]::GetFullPath($workerExecutable)
        $actualPath = [System.IO.Path]::GetFullPath($process.Path)
        if (
            [math]::Abs(($expectedStart - $actualStart).TotalSeconds) -lt 1 -and
            $expectedPath.Equals($actualPath, [StringComparison]::OrdinalIgnoreCase)
        ) {
            return $process
        }
    }
    catch {
    }
    Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
    return $null
}

function Test-Backend([object]$Config) {
    try {
        $health = Invoke-RestMethod -Uri "$($Config.server_url)/health" -TimeoutSec 5
        return $health.status -eq 'ok'
    }
    catch {
        return $false
    }
}

function Get-DeviceConnection([object]$Config) {
    try {
        $device = Invoke-RestMethod -Uri "$($Config.server_url)/api/v1/devices/$($Config.device_id)" -TimeoutSec 5
        if ($null -eq $device.worker_runtime) {
            return 'NOT_REPORTED'
        }
        return $device.worker_runtime.connection_status.ToUpperInvariant()
    }
    catch {
        return 'UNKNOWN'
    }
}

function Show-Status {
    $process = Get-RunningWorkerProcess
    $processStatus = if ($null -eq $process) { 'STOPPED' } else { 'RUNNING' }
    Write-Host ('{0,-18} {1}' -f 'Worker Process', $processStatus)
    if (-not (Test-Path -LiteralPath $configPath)) {
        Write-Host ('{0,-18} {1}' -f 'Backend', 'NOT CONFIGURED')
        Write-Host ('{0,-18} {1}' -f 'Device ID', 'NOT CONFIGURED')
        return
    }
    $config = Get-WorkerConfig
    $backendStatus = if (Test-Backend $config) { 'REACHABLE' } else { 'UNREACHABLE' }
    Write-Host ('{0,-18} {1}' -f 'Backend', $backendStatus)
    Write-Host ('{0,-18} {1}' -f 'Device ID', $config.device_id)
    Write-Host ('{0,-18} {1}' -f 'Server URL', $config.server_url)
    Write-Host ('{0,-18} {1}' -f 'Device Runtime', (Get-DeviceConnection $config))
}

function Configure-Worker {
    if ($null -ne (Get-RunningWorkerProcess)) {
        throw 'Stop the current Worker before changing its configuration.'
    }
    if ($ImportConfigPath) {
        $importPath = [System.IO.Path]::GetFullPath($ImportConfigPath)
        $import = Get-Content -Raw -Encoding UTF8 -LiteralPath $importPath | ConvertFrom-Json
        $serverUrl = [string]$import.server_url
        $deviceIdValue = [string]$import.device_id
        $token = [string]$import.device_token
        $yingdaoRoot = if ($import.PSObject.Properties.Name -contains 'yingdao_install_root') {
            [string]$import.yingdao_install_root
        }
        else {
            ''
        }
    }
    else {
        $serverUrl = Read-Host 'Backend HTTPS URL'
        $deviceIdValue = Read-Host 'Device ID'
        $secureToken = Read-Host 'Device Token (input is hidden)' -AsSecureString
        $token = Convert-SecureStringToPlainText $secureToken
        $yingdaoRoot = Read-Host 'ShadowBot install root (optional)'
        $importPath = $null
    }
    $serverUrl = Assert-ServerUrl $serverUrl.Trim()
    try {
        $deviceId = ([guid]$deviceIdValue).ToString()
    }
    catch {
        throw 'Device ID must be a valid UUID.'
    }
    if ([string]::IsNullOrWhiteSpace($token)) {
        throw 'Device Token is required.'
    }
    if ($yingdaoRoot -and -not (Test-Path -LiteralPath $yingdaoRoot -PathType Container)) {
        throw 'ShadowBot install root does not exist.'
    }

    Protect-DataDirectory
    $config = [ordered]@{
        server_url = $serverUrl
        device_id = $deviceId
        device_token_protected = Protect-Token $token
        yingdao_install_root = if ($yingdaoRoot) { [System.IO.Path]::GetFullPath($yingdaoRoot) } else { $null }
        configured_at_utc = [datetime]::UtcNow.ToString('o')
    }
    $json = $config | ConvertTo-Json
    [System.IO.File]::WriteAllText($configPath, $json, [System.Text.UTF8Encoding]::new($false))
    if ($importPath) {
        Remove-Item -LiteralPath $importPath -Force
    }
    $token = $null
    Write-Host 'Worker configuration was stored in the current user private data directory.'
    if ($StartAfterConfigure) {
        Start-Worker
    }
}

function Start-Worker {
    $config = Get-WorkerConfig
    $existing = Get-RunningWorkerProcess
    if ($null -ne $existing) {
        Write-Host "Worker is already running with PID $($existing.Id)."
        Show-Status
        return
    }
    if (-not (Test-Path -LiteralPath $workerExecutable -PathType Leaf)) {
        throw 'Packaged worker executable is missing.'
    }

    Protect-DataDirectory
    New-Item -ItemType Directory -Path $runtimeRoot, $logRoot -Force | Out-Null
    $environment = [ordered]@{
        WORKER_SERVER_URL = [string]$config.server_url
        WORKER_DEVICE_ID = [string]$config.device_id
        WORKER_DEVICE_TOKEN = Unprotect-Token ([string]$config.device_token_protected)
        WORKER_RUNTIME_ROOT = $runtimeRoot
        WORKER_LOG_DIRECTORY = $logRoot
        WORKER_LOG_MAX_BYTES = '5242880'
        WORKER_LOG_BACKUP_COUNT = '5'
        WORKER_YINGDAO_INSTALL_ROOT = if ($config.yingdao_install_root) { [string]$config.yingdao_install_root } else { $null }
    }
    $previous = @{}
    foreach ($name in $environment.Keys) {
        $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        if ($null -eq $environment[$name]) {
            [Environment]::SetEnvironmentVariable($name, $null, 'Process')
        }
        else {
            [Environment]::SetEnvironmentVariable($name, [string]$environment[$name], 'Process')
        }
    }
    try {
        $process = Start-Process `
            -FilePath $workerExecutable `
            -WorkingDirectory (Split-Path -Parent $workerExecutable) `
            -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $logRoot 'bootstrap.out.log') `
            -RedirectStandardError (Join-Path $logRoot 'bootstrap.err.log') `
            -PassThru
    }
    finally {
        foreach ($name in $environment.Keys) {
            [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process')
        }
        $environment['WORKER_DEVICE_TOKEN'] = $null
    }
    Start-Sleep -Seconds 2
    if ($process.HasExited) {
        throw "Worker exited during startup with code $($process.ExitCode). Check logs."
    }
    $state = [ordered]@{
        pid = $process.Id
        started_at_utc = $process.StartTime.ToUniversalTime().ToString('o')
        device_id = [string]$config.device_id
    }
    [System.IO.File]::WriteAllText(
        $statePath,
        ($state | ConvertTo-Json),
        [System.Text.UTF8Encoding]::new($false)
    )
    Write-Host "Worker started with PID $($process.Id)."
    Show-Status
}

function Stop-Worker {
    $process = Get-RunningWorkerProcess
    if ($null -eq $process) {
        Write-Host 'Worker is already stopped.'
        return
    }
    $processId = $process.Id
    Stop-Process -Id $processId
    $deadline = (Get-Date).AddSeconds(5)
    while ((Get-Date) -lt $deadline -and $null -ne (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
        Start-Sleep -Milliseconds 200
    }
    if ($null -ne (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
        $verified = Get-RunningWorkerProcess
        if ($null -ne $verified -and $verified.Id -eq $processId) {
            Stop-Process -Id $processId -Force
        }
    }
    Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
    Write-Host "Stopped Worker PID $processId."
}

switch ($Action) {
    'Configure' { Configure-Worker }
    'Start' { Start-Worker }
    'Stop' { Stop-Worker }
    'Status' { Show-Status }
}
