param(
    [string]$SshHost = 'control-center-dev',
    [int]$LocalPort = 18080,
    [string]$YingdaoInstallRoot,
    [string]$YingdaoDataRoot,
    [string]$YingdaoUserId,
    [string]$PublicServerUrl
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$workerPython = Join-Path $projectRoot 'worker\.venv\Scripts\python.exe'
$workerVersion = (& $workerPython -c 'from app.version import WORKER_VERSION; print(WORKER_VERSION)').Trim()
$zipPath = Join-Path $projectRoot "dist\ecommerce-worker-$workerVersion-win-x64.zip"
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) "control-center-worker-smoke-$([guid]::NewGuid().ToString('N'))"
$extractRoot = Join-Path $temporaryRoot 'package'
$dataRoot = Join-Path $temporaryRoot 'data'
$importPath = Join-Path $temporaryRoot 'worker-config.json'
$serverUrl = if ([string]::IsNullOrWhiteSpace($PublicServerUrl)) {
    "http://127.0.0.1:$LocalPort"
}
else {
    $PublicServerUrl.TrimEnd('/')
}
$tunnel = $null
$deviceId = $null
$controller = $null
$previousDataRoot = [Environment]::GetEnvironmentVariable('ECOMMERCE_WORKER_DATA_ROOT', 'Process')
if ([string]::IsNullOrWhiteSpace($YingdaoInstallRoot)) {
    $yingdaoDirectory = '{0}{1}' -f [char]0x5F71, [char]0x5200
    $YingdaoInstallRoot = Join-Path (Join-Path 'D:\' $yingdaoDirectory) 'ShadowBot'
}
if ([string]::IsNullOrWhiteSpace($YingdaoDataRoot)) {
    $YingdaoDataRoot = Join-Path $env:LOCALAPPDATA 'ShadowBot'
}
if ([string]::IsNullOrWhiteSpace($YingdaoUserId)) {
    $markedUsers = @(Get-ChildItem -LiteralPath (Join-Path $YingdaoDataRoot 'users') -Directory | Where-Object {
        $_.Name -match '^\d+$' -and
        (Test-Path -LiteralPath (Join-Path $_.FullName 'user.db3') -PathType Leaf) -and
        (Test-Path -LiteralPath (Join-Path $_.FullName 'username.ini') -PathType Leaf)
    })
    if ($markedUsers.Count -ne 1) {
        throw 'Package smoke requires one explicit or locally marked Yingdao user ID.'
    }
    $YingdaoUserId = $markedUsers[0].Name
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
    $workerExecutable = Join-Path $extractRoot 'ecommerce-worker\ecommerce-worker.exe'

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

    $tokenOutput = & ssh.exe $SshHost "docker exec control-center-backend-dev python -m app.cli.worker_token issue $deviceId"
    if ($LASTEXITCODE -ne 0) { throw 'Worker Device Token issue failed.' }
    $tokenMatch = $tokenOutput | Select-String -Pattern '^WORKER_DEVICE_TOKEN=(.+)$'
    if ($null -eq $tokenMatch -or $tokenMatch.Matches.Count -ne 1) {
        throw 'Worker Device Token output was not recognized.'
    }
    $deviceToken = $tokenMatch.Matches[0].Groups[1].Value

    $import = [ordered]@{
        server_url = $serverUrl
        device_id = $deviceId
        device_token = $deviceToken
        yingdao_install_root = $YingdaoInstallRoot
        yingdao_data_root = $YingdaoDataRoot
        yingdao_user_id = $YingdaoUserId
    } | ConvertTo-Json
    [System.IO.File]::WriteAllText($importPath, $import, [System.Text.UTF8Encoding]::new($false))
    $deviceToken = $null
    $tokenOutput = $null

    [Environment]::SetEnvironmentVariable('ECOMMERCE_WORKER_DATA_ROOT', $dataRoot, 'Process')
    $configureArguments = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $controller,
        '-Action', 'Configure', '-ImportConfigPath', $importPath
    )
    $configureArguments += if ($PublicServerUrl) { '-AllowInsecureDevelopment' } else { '-AllowInsecureLoopback' }
    & powershell.exe @configureArguments
    if ($LASTEXITCODE -ne 0) { throw 'Packaged Worker configuration failed.' }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $controller `
        -Action ConfigureYingdao `
        -YingdaoInstallRootOverride $YingdaoInstallRoot `
        -YingdaoDataRootOverride $YingdaoDataRoot `
        -YingdaoUserIdOverride $YingdaoUserId `
        -StartAfterConfigure
    if ($LASTEXITCODE -ne 0) { throw 'Packaged Yingdao configuration/start failed.' }

    Wait-Condition {
        $runtime = (Invoke-Api 'GET' "/api/v1/devices/$deviceId").worker_runtime
        return $null -ne $runtime -and $runtime.connection_status -eq 'online'
    } 35 'Packaged Worker did not become ONLINE.'

    $statePath = Join-Path $dataRoot 'worker-state.json'
    $firstPid = [int](Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json).pid
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $controller -Action Start
    if ($LASTEXITCODE -ne 0) { throw 'Second packaged Worker start check failed.' }
    $secondPid = [int](Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json).pid
    if ($firstPid -ne $secondPid) { throw 'Single-instance control started a duplicate Worker.' }

    $statusProcess = Start-Process -FilePath $workerExecutable -ArgumentList '--status-ui' -PassThru
    Start-Sleep -Seconds 2
    if ($statusProcess.HasExited) { throw 'Packaged Worker status UI exited during startup.' }
    Stop-Process -Id $statusProcess.Id

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
    Write-Host 'Single instance: PASS'
    Write-Host 'Tkinter status UI: PASS'
    Write-Host 'system.echo: SUCCESS'
    Write-Host 'system.sleep: SUCCESS'
    Write-Host "yingdao.discover: SUCCESS ($applicationCount applications)"
    Write-Host 'Runtime event upload: PASS'
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
    if ($controller -and (Test-Path -LiteralPath $controller)) {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $controller -Action Stop 2>$null | Out-Null
    }
    if ($deviceId -and $deviceId -match '^[0-9a-f-]{36}$') {
        $cleanupSql = "BEGIN; DELETE FROM task_events WHERE task_id IN (SELECT task_id FROM tasks WHERE target_device_id = '$deviceId'); DELETE FROM tasks WHERE target_device_id = '$deviceId'; DELETE FROM device_provider_inventory WHERE device_id = '$deviceId'; DELETE FROM device_runtime WHERE device_id = '$deviceId'; DELETE FROM worker_device_credentials WHERE device_id = '$deviceId'; DELETE FROM shop_device_bindings WHERE device_id = '$deviceId'; DELETE FROM devices WHERE device_id = '$deviceId'; COMMIT;"
        $cleanupBase64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($cleanupSql))
        & ssh.exe $SshHost "printf '%s' '$cleanupBase64' | base64 -d | docker exec -i control-center-postgres-dev psql -v ON_ERROR_STOP=1 -U postgres -d control_center_dev" | Out-Null
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
