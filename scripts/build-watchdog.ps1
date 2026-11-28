param(
    [string]$Python = $env:SIYU_GUARD_BUILD_PYTHON,
    [string]$OutputRoot
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $OutputRoot) { $OutputRoot = Join-Path $root 'dist' }
$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$distBoundary = [System.IO.Path]::GetFullPath((Join-Path $root 'dist')).TrimEnd('\')
if ($OutputRoot -ne $distBoundary -and -not $OutputRoot.StartsWith($distBoundary + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Watchdog build output must be inside this worktree dist directory.'
}
if (-not $Python) { $Python = Join-Path $root '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw 'Watchdog build Python is missing.' }
& $Python -c 'import PyInstaller, psutil, httpx, pydantic, tkinter'
if ($LASTEXITCODE -ne 0) { throw 'Watchdog build dependencies are missing.' }
$version = '0.1.0'
$build = Join-Path $OutputRoot '.watchdog-build'
$out = Join-Path $OutputRoot ("siyu-watchdog-$version-win-x64")
if ((Test-Path -LiteralPath $build) -or (Test-Path -LiteralPath $out)) {
    throw 'Watchdog build output already exists; preserve or remove the previous task output explicitly.'
}
New-Item -ItemType Directory -Path $build -Force | Out-Null
& $Python -m PyInstaller --noconfirm --onedir --noconsole --name siyu-watchdog `
    --distpath $build --workpath (Join-Path $build 'work') --specpath $build `
    --paths (Join-Path $root 'watchdog') --paths (Join-Path $root 'worker') `
    (Join-Path $root 'watchdog\entry.py')
if ($LASTEXITCODE -ne 0) { throw 'Watchdog packaging failed.' }
Move-Item -LiteralPath (Join-Path $build 'siyu-watchdog') -Destination $out
$check = Start-Process -FilePath (Join-Path $out 'siyu-watchdog.exe') -ArgumentList '--self-check' `
    -WindowStyle Hidden -Wait -PassThru
if ($check.ExitCode -ne 0) { throw 'Packaged Watchdog dependency check failed.' }
Copy-Item -LiteralPath (Join-Path $root 'watchdog\README.md') -Destination $out
Write-Output $out
