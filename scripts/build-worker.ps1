param(
    [switch]$SkipTests,
    [Parameter(Mandatory = $true)]
    [string]$CapabilityPublicKeyFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$workerRoot = Join-Path $projectRoot 'worker'
$workerPython = if ($env:WORKER_BUILD_PYTHON) {
    [System.IO.Path]::GetFullPath($env:WORKER_BUILD_PYTHON)
}
else {
    Join-Path $workerRoot '.venv\Scripts\python.exe'
}
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

# SkipTests never skips dependency checks: a partially installed environment
# can otherwise produce an executable that cannot start on another computer.
$dependencyCheck = @'
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import tomllib
from packaging.requirements import Requirement

project = tomllib.loads(Path('pyproject.toml').read_text(encoding='utf-8'))['project']
requirements = project['dependencies'] + [item for item in project['optional-dependencies']['dev'] if item.lower().startswith('pyinstaller')]
problems = []
for item in requirements:
    requirement = Requirement(item)
    if requirement.marker and not requirement.marker.evaluate():
        continue
    try:
        installed = version(requirement.name)
        if requirement.specifier and not requirement.specifier.contains(installed, prereleases=True):
            problems.append(requirement.name)
    except PackageNotFoundError:
        problems.append(requirement.name)
if problems:
    raise SystemExit('Worker build dependencies missing or incompatible: ' + ', '.join(sorted(problems)))
for module in ('cryptography.hazmat.primitives.asymmetric.ed25519', 'httpx', 'PIL.Image', 'pydantic_settings', 'pystray', 'PyInstaller'):
    import_module(module)
'@
Push-Location $workerRoot
try {
    $dependencyCheck | & $workerPython -
    if ($LASTEXITCODE -ne 0) { throw 'Worker build dependency check failed.' }
}
finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $CapabilityPublicKeyFile -PathType Leaf)) {
    throw 'Capability signing public key file is required for Worker release builds.'
}
$capabilityPublicKeyPath = (Resolve-Path -LiteralPath $CapabilityPublicKeyFile).ProviderPath
if ([System.IO.Path]::GetFileName($capabilityPublicKeyPath) -ne 'capability-public-key.txt') {
    throw 'Capability public key file must be named capability-public-key.txt.'
}
try {
    $capabilityPublicKey = [Convert]::FromBase64String([System.IO.File]::ReadAllText($capabilityPublicKeyPath).Trim())
    if ($capabilityPublicKey.Length -ne 32) { throw 'Invalid key length.' }
}
catch {
    throw 'Capability signing public key must be a base64 encoded 32-byte Ed25519 public key.'
}

Push-Location $workerRoot
try {
    $version = (& $workerPython -c 'from app.version import WORKER_VERSION; print(WORKER_VERSION)').Trim()
}
finally {
    Pop-Location
}
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

Push-Location $workerRoot
try {
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
        --add-data "${capabilityPublicKeyPath};." `
        (Join-Path $workerRoot 'app\__main__.py')
}
finally {
    Pop-Location
}
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller build failed.'
}

Copy-Item -Path (Join-Path $pyInstallerDist 'ecommerce-worker\*') -Destination $packageRoot -Recurse
Copy-Item -LiteralPath (Join-Path $workerRoot 'distribution\worker-control.ps1') -Destination $packageRoot
Copy-Item -LiteralPath (Join-Path $workerRoot 'distribution\README.txt') -Destination $packageRoot
$commandFiles = @(Get-ChildItem -LiteralPath (Join-Path $workerRoot 'distribution') -Filter '*.cmd')
if ($commandFiles.Count -ne 6) {
    throw 'Worker distribution must contain exactly six command wrappers.'
}
foreach ($commandFile in $commandFiles) {
    Copy-Item -LiteralPath $commandFile.FullName -Destination $packageRoot
}
[System.IO.File]::WriteAllText(
    (Join-Path $packageRoot 'VERSION'),
    "$version`r`n",
    [System.Text.UTF8Encoding]::new($false)
)

# This starts no Worker and reads no device configuration. Check the actual
# frozen runtime, including the crypto library used by signed updates.
$runtimeCheck = Start-Process -FilePath (Join-Path $packageRoot 'ecommerce-worker.exe') `
    -ArgumentList '--check-runtime-imports' -WindowStyle Hidden -PassThru
if (-not $runtimeCheck.WaitForExit(60000)) {
    Stop-Process -Id $runtimeCheck.Id -Force -ErrorAction SilentlyContinue
    throw 'Worker packaged runtime check timed out.'
}
if ($runtimeCheck.ExitCode -ne 0) { throw 'Worker packaged runtime check failed.' }

Compress-Archive -Path (Join-Path $packageRoot '*') -DestinationPath $zipPath -CompressionLevel Optimal
if (-not (Test-Path -LiteralPath $zipPath -PathType Leaf)) {
    throw 'Worker ZIP was not created.'
}

$archive = Get-Item -LiteralPath $zipPath
Write-Host "Worker package: $($archive.FullName)"
Write-Host "Worker version: $version"
Write-Host "ZIP size: $($archive.Length) bytes"
