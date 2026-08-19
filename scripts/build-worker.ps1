param(
    [switch]$SkipTests
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$workerRoot = Join-Path $projectRoot 'worker'
$workerPython = Join-Path $workerRoot '.venv\Scripts\python.exe'
$distRoot = Join-Path $projectRoot 'dist'
$buildRoot = Join-Path $distRoot '.worker-build'
$pyInstallerDist = Join-Path $buildRoot 'pyinstaller-dist'
$pyInstallerWork = Join-Path $buildRoot 'pyinstaller-work'

function Remove-VerifiedProjectChild([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }
    $resolvedProject = [System.IO.Path]::GetFullPath($projectRoot).TrimEnd('\') + '\'
    $resolvedPath = [System.IO.Path]::GetFullPath($Path)
    if (-not $resolvedPath.StartsWith($resolvedProject, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside the project: $resolvedPath"
    }
    Remove-Item -LiteralPath $resolvedPath -Recurse -Force
}

if (-not (Test-Path -LiteralPath $workerPython)) {
    throw 'Worker Python environment is missing.'
}

$version = (& $workerPython -c 'from app.version import WORKER_VERSION; print(WORKER_VERSION)').Trim()
if ($version -notmatch '^\d+\.\d+\.\d+$') {
    throw 'Worker version is invalid.'
}
$packageName = "ecommerce-worker-$version-win-x64"
$packageRoot = Join-Path $distRoot $packageName
$zipPath = Join-Path $distRoot "$packageName.zip"

Remove-VerifiedProjectChild $buildRoot
Remove-VerifiedProjectChild $packageRoot
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
New-Item -ItemType Directory -Path $buildRoot, $packageRoot -Force | Out-Null

if (-not $SkipTests) {
    Push-Location $workerRoot
    try {
        & $workerPython -m pytest -q
    }
    finally {
        Pop-Location
    }
    if ($LASTEXITCODE -ne 0) {
        throw 'Worker tests failed.'
    }
}

& $workerPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --noconsole `
    --name ecommerce-worker `
    --distpath $pyInstallerDist `
    --workpath $pyInstallerWork `
    --specpath $buildRoot `
    --paths $workerRoot `
    (Join-Path $workerRoot 'app\__main__.py')
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller build failed.'
}

Copy-Item -LiteralPath (Join-Path $pyInstallerDist 'ecommerce-worker') -Destination $packageRoot -Recurse
Copy-Item -LiteralPath (Join-Path $workerRoot 'distribution\worker-control.ps1') -Destination $packageRoot
Copy-Item -LiteralPath (Join-Path $workerRoot 'distribution\README.txt') -Destination $packageRoot
$commandFiles = @(Get-ChildItem -LiteralPath (Join-Path $workerRoot 'distribution') -Filter '*.cmd')
if ($commandFiles.Count -ne 4) {
    throw 'Worker distribution must contain exactly four command wrappers.'
}
foreach ($commandFile in $commandFiles) {
    Copy-Item -LiteralPath $commandFile.FullName -Destination $packageRoot
}
[System.IO.File]::WriteAllText(
    (Join-Path $packageRoot 'VERSION'),
    "$version`r`n",
    [System.Text.UTF8Encoding]::new($false)
)

Compress-Archive -Path (Join-Path $packageRoot '*') -DestinationPath $zipPath -CompressionLevel Optimal
if (-not (Test-Path -LiteralPath $zipPath -PathType Leaf)) {
    throw 'Worker ZIP was not created.'
}

$archive = Get-Item -LiteralPath $zipPath
Write-Host "Worker package: $($archive.FullName)"
Write-Host "Worker version: $version"
Write-Host "ZIP size: $($archive.Length) bytes"
