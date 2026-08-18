Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:ProjectRoot = Split-Path -Parent $PSScriptRoot
$script:RuntimeDirectory = Join-Path $script:ProjectRoot '.dev-runtime'
$script:BackendDirectory = Join-Path $script:ProjectRoot 'backend'
$script:FrontendDirectory = Join-Path $script:ProjectRoot 'frontend'
$script:ElectronDirectory = Join-Path $script:ProjectRoot 'electron'
$script:BackendPython = Join-Path $script:BackendDirectory '.venv\Scripts\python.exe'

function Get-DevRuntimeDirectory {
    return $script:RuntimeDirectory
}

function Get-DevStatePath([string]$Name) {
    return Join-Path $script:RuntimeDirectory "$Name.json"
}

function Save-ManagedProcess([string]$Name, [System.Diagnostics.Process]$Process) {
    New-Item -ItemType Directory -Path $script:RuntimeDirectory -Force | Out-Null
    $state = [pscustomobject]@{
        name = $Name
        rootPid = $Process.Id
        startedAtUtc = $Process.StartTime.ToUniversalTime().ToString('o')
    }
    $state | ConvertTo-Json | Set-Content -LiteralPath (Get-DevStatePath $Name) -Encoding UTF8
}

function Get-ManagedProcessState([string]$Name) {
    $path = Get-DevStatePath $Name
    if (-not (Test-Path -LiteralPath $path)) {
        return $null
    }
    try {
        return Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
    }
    catch {
        return $null
    }
}

function Remove-ManagedProcessState([string]$Name) {
    $path = Get-DevStatePath $Name
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Force
    }
}

function Test-ManagedProcessIdentity($State) {
    if ($null -eq $State) {
        return $false
    }
    $process = Get-Process -Id ([int]$State.rootPid) -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        return $false
    }
    try {
        $expected = ([datetime]$State.startedAtUtc).ToUniversalTime()
        $actual = $process.StartTime.ToUniversalTime()
        return [math]::Abs(($expected - $actual).TotalSeconds) -lt 1
    }
    catch {
        return $false
    }
}

function Get-DescendantProcessIds([int]$RootPid) {
    $processes = @(Get-CimInstance Win32_Process)
    $pending = New-Object System.Collections.Generic.Queue[int]
    $pending.Enqueue($RootPid)
    $descendants = New-Object System.Collections.Generic.List[int]
    while ($pending.Count -gt 0) {
        $parentPid = $pending.Dequeue()
        foreach ($child in $processes | Where-Object { $_.ParentProcessId -eq $parentPid }) {
            $childPid = [int]$child.ProcessId
            $descendants.Add($childPid)
            $pending.Enqueue($childPid)
        }
    }
    return @($descendants)
}

function Stop-ManagedProcess([string]$Name) {
    $state = Get-ManagedProcessState $Name
    if (-not (Test-ManagedProcessIdentity $state)) {
        Remove-ManagedProcessState $Name
        return $false
    }

    $rootPid = [int]$state.rootPid
    $descendants = @(Get-DescendantProcessIds $rootPid)
    [array]::Reverse($descendants)
    foreach ($processId in @($descendants) + @($rootPid)) {
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
    Remove-ManagedProcessState $Name
    return $true
}

function Get-ListenerProcess([int]$Port) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $listener) {
        return $null
    }
    return Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)" -ErrorAction SilentlyContinue
}

function Get-SshTunnelProcess {
    return Get-CimInstance Win32_Process -Filter "Name = 'ssh.exe'" -ErrorAction SilentlyContinue |
        Where-Object {
            $_.CommandLine -match '(^|\s)-N(\s|$)' -and
            $_.CommandLine -match 'control-center-dev'
        } |
        Select-Object -First 1
}

function Test-PostgreSqlConnection {
    $alembic = Join-Path $script:BackendDirectory '.venv\Scripts\alembic.exe'
    if (-not (Test-Path -LiteralPath $alembic)) {
        return $false
    }
    try {
        $probe = Start-Process `
            -FilePath $alembic `
            -ArgumentList @('current') `
            -WorkingDirectory $script:BackendDirectory `
            -WindowStyle Hidden `
            -PassThru
        if (-not $probe.WaitForExit(5000)) {
            $probe.Kill($true)
            $probe.WaitForExit()
            return $false
        }
        return $probe.ExitCode -eq 0
    }
    catch {
        return $false
    }
}

function Test-BackendHealth {
    try {
        $response = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2
        return $response.status -eq 'ok'
    }
    catch {
        return $false
    }
}

function Test-FrontendReal {
    try {
        $response = Invoke-WebRequest -Uri 'http://127.0.0.1:5173' -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -ne 200) {
            return $false
        }
    }
    catch {
        return $false
    }
    $listener = Get-ListenerProcess 5173
    if ($null -eq $listener) {
        return $false
    }
    $normalizedCommandLine = $listener.CommandLine.Replace('"', '')
    return $normalizedCommandLine -match '--mode(?:=|\s+)real'
}

function Test-ElectronRunning {
    return $null -ne (Get-ElectronMainProcess)
}

function Get-ElectronMainProcess {
    $escapedAppPath = [regex]::Escape($script:ElectronDirectory)
    $renderer = Get-CimInstance Win32_Process -Filter "Name = 'electron.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match "--app-path=.?$escapedAppPath" } |
        Select-Object -First 1
    if ($null -eq $renderer) {
        return $null
    }
    return Get-Process -Id ([int]$renderer.ParentProcessId) -ErrorAction SilentlyContinue
}

function Wait-DevCondition(
    [scriptblock]$Condition,
    [int]$TimeoutSeconds,
    [string]$FailureMessage
) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (& $Condition) {
            return
        }
        Start-Sleep -Milliseconds 300
    }
    throw $FailureMessage
}

function Start-DevProcess(
    [string]$Name,
    [string]$FilePath,
    [string[]]$ArgumentList,
    [string]$WorkingDirectory
) {
    New-Item -ItemType Directory -Path $script:RuntimeDirectory -Force | Out-Null
    $stdout = Join-Path $script:RuntimeDirectory "$Name.out.log"
    $stderr = Join-Path $script:RuntimeDirectory "$Name.err.log"
    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru
    Save-ManagedProcess $Name $process
    return $process
}

function Write-DevStatus(
    [string]$Label,
    [bool]$Running,
    [string]$RunningText = 'RUNNING',
    [string]$StoppedText = 'STOPPED'
) {
    $state = if ($Running) { $RunningText } else { $StoppedText }
    Write-Host ('{0,-14} {1}' -f $Label, $state)
}
