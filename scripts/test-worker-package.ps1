param(
    [string]$SshHost = 'control-center-dev',
    [int]$LocalPort = 18080,
    [string]$YingdaoInstallRoot,
    [string]$PublicServerUrl,
    [switch]$SkipYingdaoDiscovery,
    [ValidateRange(0, 3600)]
    [int]$SustainedRunSeconds = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$workerPython = Join-Path $projectRoot 'worker\.venv\Scripts\python.exe'
$backendPython = Join-Path $projectRoot 'backend\.venv\Scripts\python.exe'
$workerVersion = (& $workerPython -c 'from app.version import WORKER_VERSION; print(WORKER_VERSION)').Trim()
$zipPath = Join-Path $projectRoot "dist\ecommerce-worker-$workerVersion-win-x64.zip"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) "control-center-worker-smoke-$([guid]::NewGuid().ToString('N'))"
$extractRoot = Join-Path $temporaryRoot 'package'
$dataRoot = Join-Path $temporaryRoot 'data'
$serverUrl = if ([string]::IsNullOrWhiteSpace($PublicServerUrl)) {
    "http://127.0.0.1:$LocalPort"
}
else {
    $PublicServerUrl.TrimEnd('/')
}
$tunnel = $null
$deviceId = $null
$controller = $null
$guiProcess = $null
$statusProcess = $null
$previousDataRoot = [Environment]::GetEnvironmentVariable('ECOMMERCE_WORKER_DATA_ROOT', 'Process')
if ([string]::IsNullOrWhiteSpace($YingdaoInstallRoot)) {
    $yingdaoDirectory = '{0}{1}' -f [char]0x5F71, [char]0x5200
    $YingdaoInstallRoot = Join-Path (Join-Path 'D:\' $yingdaoDirectory) 'ShadowBot'
}
function Wait-Condition([scriptblock]$Condition, [int]$TimeoutSeconds, [string]$Message) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (& $Condition) { return }
        Start-Sleep -Milliseconds 500
    }
    throw $Message
}

function Invoke-Api([string]$Method, [string]$Path, [object]$Body = $null) {
    $parameters = @{
        Method = $Method
        Uri = "$serverUrl$Path"
        TimeoutSec = 10
    }
    if ($null -ne $Body) {
        $parameters.ContentType = 'application/json'
        $parameters.Body = $Body | ConvertTo-Json -Depth 10 -Compress
    }
    return Invoke-RestMethod @parameters
}

function Wait-Task([string]$TaskId) {
    $script:taskResult = $null
    Wait-Condition {
        $script:taskResult = Invoke-Api 'GET' "/api/v1/tasks/$TaskId"
        return $script:taskResult.status -in @('success', 'failed', 'lost')
    } 45 "Task $TaskId did not finish."
    if ($script:taskResult.status -ne 'success') {
        throw "Task $TaskId ended as $($script:taskResult.status): $($script:taskResult.error_code)"
    }
    return $script:taskResult
}

try {
    if (-not (Test-Path -LiteralPath $zipPath -PathType Leaf)) {
        throw 'Worker ZIP is missing. Run scripts/build-worker.ps1 first.'
    }
    if (-not $PublicServerUrl -and $null -ne (Get-NetTCPConnection -State Listen -LocalPort $LocalPort -ErrorAction SilentlyContinue)) {
        throw "Local test port $LocalPort is already in use."
    }

    New-Item -ItemType Directory -Path $extractRoot -Force | Out-Null
    Expand-Archive -LiteralPath $zipPath -DestinationPath $extractRoot
    $forbiddenFiles = @(Get-ChildItem -LiteralPath $extractRoot -Recurse -Force | Where-Object {
        $_.Name -match '(^\.env$|\.key$|id_rsa|id_ed25519|(^|[-_.])tests?($|[-_.]))'
    })
    if ($forbiddenFiles.Count -gt 0) {
        throw 'Worker ZIP contains a forbidden development or secret-bearing file.'
    }
    $textFiles = @(Get-ChildItem -LiteralPath $extractRoot -Recurse -File | Where-Object {
        $_.Extension -in @('.txt', '.ps1', '.cmd', '.json', '.pem') -or $_.Name -eq 'VERSION'
    })
    if ($textFiles | Select-String -Pattern 'postgresql://|BACKEND_DATABASE_URL=|WORKER_DEVICE_TOKEN=|BEGIN [A-Z ]*PRIVATE KEY') {
        throw 'Worker ZIP text content contains a forbidden secret or database pattern.'
    }
    $controller = Join-Path $extractRoot 'worker-control.ps1'
    $workerExecutable = Join-Path $extractRoot 'ecommerce-worker.exe'

    if (-not $PublicServerUrl) {
        $tunnel = Start-Process -FilePath 'ssh.exe' -ArgumentList @(
            '-N', '-T', '-L', "$LocalPort`:127.0.0.1:18000", $SshHost
        ) -WindowStyle Hidden -PassThru
    }
    Wait-Condition {
        try { return (Invoke-RestMethod -Uri "$serverUrl/health" -TimeoutSec 2).status -eq 'ok' } catch { return $false }
    } 20 'SSH-forwarded VPS Backend did not become healthy.'

    $device = Invoke-Api 'POST' '/api/v1/devices' @{
        display_name = 'Worker package smoke test'
        location = 'temporary clean directory'
        note = 'Stage 3B-1B automated cleanup'
    }
    $deviceId = [string]$device.device_id

    $issuedCredential = Invoke-Api 'POST' "/api/v1/devices/$deviceId/worker-credential/issue"
    $deviceToken = [string]$issuedCredential.token
    $provisioning = Invoke-RestMethod `
        -Uri "$serverUrl/api/v1/worker/provisioning" `
        -Headers @{ Authorization = "Bearer $deviceToken" } `
        -TimeoutSec 10
    if ([string]$provisioning.device_id -ne $deviceId) {
        throw 'Worker Token resolved an unexpected Device identity.'
    }

    [Environment]::SetEnvironmentVariable('ECOMMERCE_WORKER_DATA_ROOT', $dataRoot, 'Process')
    $provisionPayload = [ordered]@{
        server_url = $serverUrl
        device_token = $deviceToken
        yingdao_install_root = if ($SkipYingdaoDiscovery) { '' } else { $YingdaoInstallRoot }
    } | ConvertTo-Json
    Push-Location (Join-Path $projectRoot 'worker')
    try {
        $provisionPayload | & $workerPython -m tools.provisioning_smoke_config
    }
    finally {
        Pop-Location
    }
    if ($LASTEXITCODE -ne 0) { throw 'Production Config Service provisioning failed.' }
    $deviceToken = $null
    $issuedCredential = $null
    $provisionPayload = $null

    $guiProcess = Start-Process -FilePath $workerExecutable -WindowStyle Hidden -PassThru

    Wait-Condition {
        $runtime = (Invoke-Api 'GET' "/api/v1/devices/$deviceId").worker_runtime
        return $null -ne $runtime -and $runtime.connection_status -eq 'online'
    } 35 'Packaged Worker did not become ONLINE.'
    Wait-Condition {
        $skills = @(Invoke-Api 'GET' "/api/v1/devices/$deviceId/skill-capabilities")
        $skillIds = @(
            foreach ($responseItem in $skills) {
                foreach ($skill in @($responseItem)) {
                    if ($skill.PSObject.Properties.Name -contains 'skill_id') {
                        [string]$skill.skill_id
                    }
                }
            }
        )
        $missingSkills = @(
            @('system.echo', 'system.sleep', 'yingdao.app.run') |
                Where-Object { $_ -notin $skillIds }
        )
        return $missingSkills.Count -eq 0
    } 20 'Packaged Worker did not synchronize its Skill Registry snapshot.'

    $statePath = Join-Path $dataRoot 'worker-state.json'
    $firstPid = [int](Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json).pid
    Stop-Process -Id $guiProcess.Id
    $guiProcess = $null
    Start-Sleep -Seconds 1
    if ($null -eq (Get-Process -Id $firstPid -ErrorAction SilentlyContinue)) {
        throw 'Closing the Tkinter GUI stopped the Worker Core.'
    }
    $runtimeAfterGuiClose = (Invoke-Api 'GET' "/api/v1/devices/$deviceId").worker_runtime
    if ($runtimeAfterGuiClose.connection_status -ne 'online') {
        throw 'Worker became OFFLINE after closing the Tkinter GUI.'
    }

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $controller -Action Start
    if ($LASTEXITCODE -ne 0) { throw 'Second packaged Worker start check failed.' }
    $secondPid = [int](Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json).pid
    if ($firstPid -ne $secondPid) { throw 'Single-instance control started a duplicate Worker.' }

    $statusProcess = Start-Process -FilePath $workerExecutable -WindowStyle Hidden -PassThru
    Start-Sleep -Seconds 2
    if ($statusProcess.HasExited) { throw 'Packaged Worker status UI exited during startup.' }
    Stop-Process -Id $statusProcess.Id
    $statusProcess = $null

    $echoTask = Invoke-Api 'POST' '/api/v1/tasks' @{
        target_device_id = $deviceId
        skill_id = 'system.echo'
        input = @{ message = 'packaged-worker-ok' }
    }
    $echoResult = Wait-Task ([string]$echoTask.task_id)
    if ($echoResult.result.message -ne 'packaged-worker-ok') { throw 'system.echo returned an unexpected result.' }
    $echoEvents = Invoke-Api 'GET' "/api/v1/tasks/$($echoTask.task_id)/events?after_seq=0&limit=100"
    if (@($echoEvents.items).Count -lt 2 -or @($echoEvents.items)[-1].event_type -ne 'completed') {
        throw 'system.echo runtime events were not persisted through the packaged Worker.'
    }

    $sleepTask = Invoke-Api 'POST' '/api/v1/tasks' @{
        target_device_id = $deviceId
        skill_id = 'system.sleep'
        input = @{ seconds = 0.5 }
    }
    $sleepResult = Wait-Task ([string]$sleepTask.task_id)

    $applicationCount = $null
    if (-not $SkipYingdaoDiscovery) {
        $discoveryTask = Invoke-Api 'POST' '/api/v1/tasks' @{
            target_device_id = $deviceId
            skill_id = 'yingdao.discover'
            input = @{}
        }
        $discoveryResult = Wait-Task ([string]$discoveryTask.task_id)
        $applicationCount = @($discoveryResult.result.applications).Count
        if ($discoveryResult.result.available -ne $true) { throw 'yingdao.discover did not report an available provider.' }
        $discoveryEvents = Invoke-Api 'GET' "/api/v1/tasks/$($discoveryTask.task_id)/events?after_seq=0&limit=100"
        if (@($discoveryEvents.items).Count -lt 2 -or @($discoveryEvents.items)[-1].event_type -ne 'completed') {
            throw 'yingdao.discover runtime events were not persisted through the packaged Worker.'
        }
    }

    if ($SustainedRunSeconds -gt 0) {
        $deadline = (Get-Date).AddSeconds($SustainedRunSeconds)
        while ((Get-Date) -lt $deadline) {
            $state = Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json
            if ($null -eq (Get-Process -Id ([int]$state.pid) -ErrorAction SilentlyContinue)) {
                throw 'Packaged Worker exited during the sustained runtime check.'
            }
            $runtime = (Invoke-Api 'GET' "/api/v1/devices/$deviceId").worker_runtime
            if ($null -eq $runtime -or $runtime.connection_status -ne 'online') {
                throw 'Packaged Worker became OFFLINE during the sustained runtime check.'
            }
            Start-Sleep -Seconds ([math]::Min(5, [math]::Max(1, ($deadline - (Get-Date)).TotalSeconds)))
        }
    }

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $controller -Action Stop
    if ($LASTEXITCODE -ne 0) { throw 'Packaged Worker stop failed.' }
    Wait-Condition {
        $runtime = (Invoke-Api 'GET' "/api/v1/devices/$deviceId").worker_runtime
        return $null -ne $runtime -and $runtime.connection_status -eq 'offline'
    } 70 'Device did not become OFFLINE after stopping the packaged Worker.'

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $controller -Action Start
    if ($LASTEXITCODE -ne 0) { throw 'Packaged Worker restart failed.' }
    Wait-Condition {
        $runtime = (Invoke-Api 'GET' "/api/v1/devices/$deviceId").worker_runtime
        return $null -ne $runtime -and $runtime.connection_status -eq 'online'
    } 35 'Device did not return ONLINE with the stored Token.'

    Write-Host 'Package clean extraction: PASS'
    Write-Host 'Packaged Worker ONLINE: PASS'
    Write-Host 'Skill Registry snapshot: PASS'
    Write-Host 'Single instance: PASS'
    Write-Host 'Tkinter GUI provisioning and close independence: PASS'
    Write-Host 'system.echo: SUCCESS'
    Write-Host 'system.sleep: SUCCESS'
    if ($SkipYingdaoDiscovery) {
        Write-Host 'yingdao.discover: SKIPPED (no local 6.3.6 runtime)'
    }
    else {
        Write-Host "yingdao.discover: SUCCESS ($applicationCount applications)"
    }
    Write-Host 'Runtime event upload: PASS'
    if ($SustainedRunSeconds -gt 0) {
        Write-Host "Sustained package runtime: PASS ($SustainedRunSeconds seconds)"
    }
    Write-Host 'OFFLINE and stored-token recovery: PASS'
}
catch {
    Write-Warning "Worker package smoke failed: $($_.Exception.Message)"
    if (Test-Path -LiteralPath (Join-Path $dataRoot 'logs')) {
        Get-ChildItem -LiteralPath (Join-Path $dataRoot 'logs') -File | ForEach-Object {
            Write-Warning "Worker log tail: $($_.Name)"
            Get-Content -LiteralPath $_.FullName -Tail 40 | ForEach-Object {
                Write-Warning $_
            }
        }
    }
    throw
}
finally {
    foreach ($process in @($guiProcess, $statusProcess)) {
        if ($null -ne $process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
        }
    }
    if ($controller -and (Test-Path -LiteralPath $controller)) {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $controller -Action Stop 2>$null | Out-Null
    }
    if ($deviceId -and $deviceId -match '^[0-9a-f-]{36}$') {
        $cleanupCompleted = $false
        if (Test-Path -LiteralPath $backendPython -PathType Leaf) {
            $cleanupCode = @'
import os
from uuid import UUID
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.core.database import get_database_engine
from app.modules.devices.models import Device
from app.modules.shops.models import ShopDeviceBinding
from app.modules.tasks.models import Task, TaskEvent
from app.modules.workers.models import DeviceProviderInventory, DeviceRuntime, DeviceSkillCapability, WorkerDeviceCredential
device_id = UUID(os.environ["WORKER_SMOKE_DEVICE_ID"])
with Session(get_database_engine()) as session:
    task_ids = select(Task.task_id).where(Task.target_device_id == device_id)
    session.execute(delete(TaskEvent).where(TaskEvent.task_id.in_(task_ids)))
    session.execute(delete(Task).where(Task.target_device_id == device_id))
    session.execute(delete(DeviceSkillCapability).where(DeviceSkillCapability.device_id == device_id))
    session.execute(delete(DeviceProviderInventory).where(DeviceProviderInventory.device_id == device_id))
    session.execute(delete(DeviceRuntime).where(DeviceRuntime.device_id == device_id))
    session.execute(delete(WorkerDeviceCredential).where(WorkerDeviceCredential.device_id == device_id))
    session.execute(delete(ShopDeviceBinding).where(ShopDeviceBinding.device_id == device_id))
    session.execute(delete(Device).where(Device.device_id == device_id))
    session.commit()
'@
            $previousSmokeDeviceId = [Environment]::GetEnvironmentVariable('WORKER_SMOKE_DEVICE_ID', 'Process')
            try {
                [Environment]::SetEnvironmentVariable('WORKER_SMOKE_DEVICE_ID', $deviceId, 'Process')
                Push-Location (Join-Path $projectRoot 'backend')
                try {
                    $cleanupCode | & $backendPython -
                    $cleanupCompleted = $LASTEXITCODE -eq 0
                }
                finally {
                    Pop-Location
                }
            }
            catch {
                Write-Warning "Local Worker smoke cleanup failed: $($_.Exception.Message)"
            }
            finally {
                [Environment]::SetEnvironmentVariable('WORKER_SMOKE_DEVICE_ID', $previousSmokeDeviceId, 'Process')
            }
        }
        if (-not $cleanupCompleted) {
            $cleanupSql = "BEGIN; DELETE FROM task_events WHERE task_id IN (SELECT task_id FROM tasks WHERE target_device_id = '$deviceId'); DELETE FROM tasks WHERE target_device_id = '$deviceId'; DELETE FROM device_skill_capabilities WHERE device_id = '$deviceId'; DELETE FROM device_provider_inventory WHERE device_id = '$deviceId'; DELETE FROM device_runtime WHERE device_id = '$deviceId'; DELETE FROM worker_device_credentials WHERE device_id = '$deviceId'; DELETE FROM shop_device_bindings WHERE device_id = '$deviceId'; DELETE FROM devices WHERE device_id = '$deviceId'; COMMIT;"
            $cleanupBase64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($cleanupSql))
            & ssh.exe -o BatchMode=yes -o ConnectTimeout=5 $SshHost "printf '%s' '$cleanupBase64' | base64 -d | docker exec -i control-center-postgres-dev psql -v ON_ERROR_STOP=1 -U postgres -d control_center_dev" | Out-Null
        }
    }
    if ($null -ne $tunnel -and -not $tunnel.HasExited) {
        Stop-Process -Id $tunnel.Id -Force
    }
    [Environment]::SetEnvironmentVariable('ECOMMERCE_WORKER_DATA_ROOT', $previousDataRoot, 'Process')
    if (Test-Path -LiteralPath $temporaryRoot) {
        $resolvedTemporaryRoot = [System.IO.Path]::GetFullPath($temporaryRoot)
        $resolvedSystemTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
        if ($resolvedTemporaryRoot.StartsWith($resolvedSystemTemp, [StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $resolvedTemporaryRoot -Recurse -Force
        }
    }
}
