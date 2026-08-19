param(
    [string]$SshHost = 'control-center-dev',
    [string]$RemoteRoot = '/opt/ecommerce-control-center/backend',
    [switch]$SkipTests,
    [switch]$AllowInsecurePublicHttp
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $projectRoot 'backend'
$backendPython = Join-Path $backendRoot '.venv\Scripts\python.exe'
$backendEnvironment = Join-Path $backendRoot '.env'
$remoteScript = Join-Path $PSScriptRoot 'remote-deploy-backend-dev.sh'
$releaseTimestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) "control-center-backend-$([guid]::NewGuid().ToString('N'))"
$stagingRoot = Join-Path $temporaryRoot 'release'
$archivePath = Join-Path $temporaryRoot 'release.tar.gz'
$backendBindHost = if ($AllowInsecurePublicHttp) { '0.0.0.0' } else { '127.0.0.1' }
$backendBindPort = if ($AllowInsecurePublicHttp) { 8000 } else { 18000 }

if ($RemoteRoot -ne '/opt/ecommerce-control-center/backend') {
    throw 'RemoteRoot must remain inside /opt/ecommerce-control-center/backend.'
}
foreach ($command in @('ssh.exe', 'scp.exe', 'tar.exe')) {
    if ($null -eq (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "$command is required."
    }
}
if (-not (Test-Path -LiteralPath $backendEnvironment)) {
    throw 'backend/.env is required to initialize the server environment.'
}
if (-not (Test-Path -LiteralPath $backendPython)) {
    throw 'Backend Python environment is missing.'
}

try {
    if (-not $SkipTests) {
        Push-Location $backendRoot
        try {
            & $backendPython -m pytest -q
        }
        finally {
            Pop-Location
        }
        if ($LASTEXITCODE -ne 0) {
            throw 'Backend tests failed.'
        }
    }

    New-Item -ItemType Directory -Path $stagingRoot -Force | Out-Null
    foreach ($file in @('Dockerfile', '.dockerignore', 'compose.yaml', 'pyproject.toml', 'alembic.ini')) {
        Copy-Item -LiteralPath (Join-Path $backendRoot $file) -Destination $stagingRoot
    }
    foreach ($directory in @('app', 'migrations', 'deploy')) {
        Copy-Item -LiteralPath (Join-Path $backendRoot $directory) -Destination $stagingRoot -Recurse
    }
    & tar.exe -czf $archivePath -C $stagingRoot .
    if ($LASTEXITCODE -ne 0) {
        throw 'Backend release archive creation failed.'
    }
    $contentHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $archivePath).Hash.Substring(0, 7).ToLowerInvariant()
    $releaseId = "$releaseTimestamp-$contentHash"
    $remoteArchive = "/tmp/control-center-backend-$releaseId.tar.gz"
    $remoteDeployScript = "/tmp/control-center-deploy-$releaseId.sh"

    & ssh.exe $SshHost "install -d -m 0750 '$RemoteRoot'"
    if ($LASTEXITCODE -ne 0) {
        throw 'Remote deployment directory preparation failed.'
    }

    & ssh.exe $SshHost "test -f '$RemoteRoot/.env'"
    $remoteEnvironmentExists = $LASTEXITCODE -eq 0
    if (-not $remoteEnvironmentExists) {
        $values = @{}
        foreach ($line in Get-Content -LiteralPath $backendEnvironment) {
            if ($line -match '^([A-Z0-9_]+)=(.*)$') {
                $values[$Matches[1]] = $Matches[2]
            }
        }
        foreach ($required in @('BACKEND_DATABASE_URL', 'BACKEND_ENCRYPTION_KEY')) {
            if (-not $values.ContainsKey($required) -or [string]::IsNullOrWhiteSpace($values[$required])) {
                throw "$required is missing from backend/.env."
            }
        }
        $serverDatabaseUrl = $values['BACKEND_DATABASE_URL']
        if ($serverDatabaseUrl -notmatch '@(?:127\.0\.0\.1|localhost):35433/control_center_dev(?:\?|$)') {
            throw 'The development database URL must use the existing VPS loopback PostgreSQL binding.'
        }
        $serverEnvironmentPath = Join-Path $temporaryRoot 'backend.env'
        $serverEnvironmentLines = @(
            "BACKEND_DATABASE_URL=$serverDatabaseUrl",
            "BACKEND_ENCRYPTION_KEY=$($values['BACKEND_ENCRYPTION_KEY'])",
            'BACKEND_WORKER_ONLINE_TIMEOUT_SECONDS=45',
            'BACKEND_WORKER_TASK_LEASE_SECONDS=60',
            'BACKEND_WORKER_RECONCILE_INTERVAL_SECONDS=10'
        )
        [System.IO.File]::WriteAllLines($serverEnvironmentPath, $serverEnvironmentLines, [System.Text.UTF8Encoding]::new($false))
        & scp.exe $serverEnvironmentPath "${SshHost}:/tmp/control-center-backend-$releaseId.env"
        if ($LASTEXITCODE -ne 0) {
            throw 'Server environment upload failed.'
        }
        & ssh.exe $SshHost "install -m 0600 '/tmp/control-center-backend-$releaseId.env' '$RemoteRoot/.env' && rm -f '/tmp/control-center-backend-$releaseId.env'"
        if ($LASTEXITCODE -ne 0) {
            throw 'Server environment installation failed.'
        }
        Write-Host 'Initialized server environment with restricted permissions; secrets were not printed.'
    }
    else {
        Write-Host 'Reusing existing server environment.'
    }

    & scp.exe $archivePath "${SshHost}:$remoteArchive"
    if ($LASTEXITCODE -ne 0) {
        throw 'Backend release upload failed.'
    }
    & scp.exe $remoteScript "${SshHost}:$remoteDeployScript"
    if ($LASTEXITCODE -ne 0) {
        throw 'Remote deployment script upload failed.'
    }
    if ($AllowInsecurePublicHttp) {
        Write-Warning 'Deploying the DEV Backend over public plaintext HTTP. Worker tokens are not protected in transit.'
    }
    & ssh.exe $SshHost "chmod 0700 '$remoteDeployScript' && '$remoteDeployScript' '$RemoteRoot' '$remoteArchive' '$releaseId' '$backendBindHost' '$backendBindPort'; status=`$?; rm -f '$remoteDeployScript'; exit `$status"
    if ($LASTEXITCODE -ne 0) {
        throw 'Remote Backend deployment failed.'
    }
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        $resolvedTemporaryRoot = [System.IO.Path]::GetFullPath($temporaryRoot)
        $resolvedSystemTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
        if (-not $resolvedTemporaryRoot.StartsWith($resolvedSystemTemp, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw 'Refusing to remove a temporary directory outside the system temp root.'
        }
        Remove-Item -LiteralPath $resolvedTemporaryRoot -Recurse -Force
    }
}
