param([string]$ZipPath)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$projectRoot = Split-Path -Parent $PSScriptRoot
$versionSource = [System.IO.File]::ReadAllText((Join-Path $projectRoot 'worker\app\version.py'))
if ($versionSource -notmatch 'WORKER_VERSION\s*=\s*["''](\d+\.\d+\.\d+)["'']') {
    throw 'Cannot determine Worker version.'
}
$workerVersion = $Matches[1]
if ([string]::IsNullOrWhiteSpace($ZipPath)) {
    $ZipPath = Join-Path $projectRoot "dist\ecommerce-worker-$workerVersion-win-x64.zip"
}
if (-not (Test-Path -LiteralPath $ZipPath -PathType Leaf)) { throw 'Worker ZIP does not exist.' }
$archive = [System.IO.Compression.ZipFile]::OpenRead((Resolve-Path -LiteralPath $ZipPath).ProviderPath)
try {
    $names = @($archive.Entries | ForEach-Object { $_.FullName.Replace('\', '/') })
    foreach ($required in @('ecommerce-worker.exe', 'worker-control.ps1', 'README.txt', 'VERSION')) {
        if ($required -notin $names) { throw "Worker ZIP is missing $required." }
    }
    $retiredLabel = [string]::Concat([char]0x5F71, [char]0x5200)
    $forbiddenCount = @($names | Where-Object {
        $_ -match '(?i)(^|/)(\.env|id_rsa|id_ed25519)(/|$)|\.key$|shadowbot|yingdao' -or $_.Contains($retiredLabel)
    }).Count
    if ($forbiddenCount -gt 0) { throw 'Worker ZIP contains retired or secret-bearing files.' }
}
finally { $archive.Dispose() }
$packageRoot = Join-Path $projectRoot "dist\ecommerce-worker-$workerVersion-win-x64"
if (-not (Test-Path -LiteralPath $packageRoot -PathType Container)) {
    throw 'Unpacked build output is needed for the executable self-check.'
}
if (([System.IO.File]::ReadAllText((Join-Path $packageRoot 'VERSION')).Trim()) -ne $workerVersion) {
    throw 'Unpacked Worker version does not match source.'
}
$tokens = $null
$parseErrors = $null
[void][System.Management.Automation.Language.Parser]::ParseFile((Join-Path $packageRoot 'worker-control.ps1'), [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -gt 0) { throw 'Worker control script has a syntax error.' }
$executable = Join-Path $packageRoot 'ecommerce-worker.exe'
foreach ($arguments in @("--check-version $workerVersion", '--check-capability-trust')) {
    $process = Start-Process -FilePath $executable -ArgumentList $arguments -WindowStyle Hidden -PassThru -Wait
    if ($process.ExitCode -ne 0) { throw 'Worker executable self-check failed.' }
}
Write-Host "Worker $workerVersion package and signing trust: PASS"
Write-Host 'Offline check only: no server, device, or task was modified.'
