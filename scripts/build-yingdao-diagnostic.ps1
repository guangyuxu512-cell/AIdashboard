Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$workerRoot = Join-Path $projectRoot 'worker'
$workerPython = Join-Path $workerRoot '.venv\Scripts\python.exe'
$distRoot = Join-Path $projectRoot 'dist'
$buildRoot = Join-Path $distRoot '.yingdao-diagnostic-build'
$packageRoot = Join-Path $distRoot 'yingdao-readonly-diagnostic-win-x64'
$zipPath = Join-Path $distRoot 'yingdao-readonly-diagnostic-win-x64.zip'

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

if (-not (Test-Path -LiteralPath $workerPython -PathType Leaf)) {
    throw 'Worker Python environment is missing.'
}

Remove-VerifiedProjectChild $buildRoot
Remove-VerifiedProjectChild $packageRoot
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
New-Item -ItemType Directory -Path $buildRoot, $packageRoot -Force | Out-Null

Push-Location $workerRoot
try {
    & $workerPython -m pytest -q tests\test_yingdao_diagnostic.py
}
finally {
    Pop-Location
}
if ($LASTEXITCODE -ne 0) {
    throw 'Yingdao diagnostic tests failed.'
}

& $workerPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --console `
    --name yingdao-diagnostic `
    --distpath $packageRoot `
    --workpath (Join-Path $buildRoot 'work') `
    --specpath $buildRoot `
    --paths $workerRoot `
    (Join-Path $workerRoot 'tools\yingdao_diagnostic.py')
if ($LASTEXITCODE -ne 0) {
    throw 'Yingdao diagnostic executable build failed.'
}

$commandFiles = @(Get-ChildItem -LiteralPath (Join-Path $workerRoot 'tools') -Filter '*.cmd')
if ($commandFiles.Count -ne 1) {
    throw 'Yingdao diagnostic tools must contain exactly one CMD entrypoint.'
}
Copy-Item -LiteralPath $commandFiles[0].FullName -Destination $packageRoot
Copy-Item -LiteralPath (Join-Path $workerRoot 'tools\README.txt') -Destination $packageRoot
Compress-Archive -Path (Join-Path $packageRoot '*') -DestinationPath $zipPath -CompressionLevel Optimal

$archive = Get-Item -LiteralPath $zipPath
Write-Host "Yingdao diagnostic package: $($archive.FullName)"
Write-Host "ZIP size: $($archive.Length) bytes"
