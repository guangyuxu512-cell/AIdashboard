[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Get-Sha256Hex {
    param(
        [Parameter(Mandatory = $true)]
        [string]$LiteralPath
    )

    $resolvedPath = (Resolve-Path -LiteralPath $LiteralPath).Path
    $sha256Algorithm = [Security.Cryptography.SHA256]::Create()
    $fileStream = [IO.File]::OpenRead($resolvedPath)
    try {
        $hashBytes = $sha256Algorithm.ComputeHash($fileStream)
    } finally {
        $fileStream.Dispose()
        $sha256Algorithm.Dispose()
    }
    return (($hashBytes | ForEach-Object { $_.ToString('x2') }) -join '')
}

function Get-PeMetadata {
    param(
        [Parameter(Mandatory = $true)]
        [string]$LiteralPath
    )

    $resolvedPath = (Resolve-Path -LiteralPath $LiteralPath).Path
    $fileStream = [IO.File]::OpenRead($resolvedPath)
    $reader = [IO.BinaryReader]::new($fileStream)
    try {
        if ($reader.ReadUInt16() -ne 0x5a4d) {
            throw "PE 文件缺少 MZ header：$resolvedPath"
        }
        $fileStream.Position = 0x3c
        $peOffset = $reader.ReadInt32()
        $fileStream.Position = $peOffset
        if ($reader.ReadUInt32() -ne 0x00004550) {
            throw "PE 文件缺少 PE signature：$resolvedPath"
        }
        $machine = $reader.ReadUInt16()
        $fileStream.Position = $peOffset + 24
        $optionalHeaderMagic = $reader.ReadUInt16()
        if ($optionalHeaderMagic -eq 0x20b) {
            $dataDirectoryOffset = $peOffset + 24 + 112
        } elseif ($optionalHeaderMagic -eq 0x10b) {
            $dataDirectoryOffset = $peOffset + 24 + 96
        } else {
            throw ('PE optional header 类型未知：0x{0:X4}' -f $optionalHeaderMagic)
        }
        $fileStream.Position = $dataDirectoryOffset + (8 * 4)
        $certificateTableOffset = $reader.ReadUInt32()
        $certificateTableSize = $reader.ReadUInt32()
    } finally {
        $reader.Dispose()
        $fileStream.Dispose()
    }

    [pscustomobject]@{
        Machine = $machine
        AuthenticodeStatus = if ($certificateTableOffset -eq 0 -and $certificateTableSize -eq 0) {
            'NotSigned'
        } else {
            'SignaturePresent'
        }
    }
}

$electronPath = Split-Path -Parent $PSScriptRoot
$repositoryPath = (Resolve-Path -LiteralPath (Join-Path $electronPath '..')).Path

if (-not [Environment]::Is64BitOperatingSystem) {
    throw 'Windows x64 安装包必须在 64 位 Windows 构建机上生成'
}

$nodeVersionText = (& node --version).Trim().TrimStart('v')
if ($LASTEXITCODE -ne 0 -or [Version]$nodeVersionText -lt [Version]'22.12.0') {
    throw 'Windows 发行构建需要 Node.js >=22.12.0'
}

$sourceSha = (& git -C $repositoryPath rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $sourceSha -notmatch '^[0-9a-f]{40}$') {
    throw '无法解析发行包源提交 SHA'
}
$workingTreeChanges = & git -C $repositoryPath status --porcelain --untracked-files=all
if ($LASTEXITCODE -ne 0) {
    throw '无法检查工作树状态'
}
if ($workingTreeChanges) {
    throw '正式发行包只能从干净的已提交工作树构建'
}

$packageMetadata = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $electronPath 'package.json') |
    ConvertFrom-Json
$sourceShortSha = $sourceSha.Substring(0, 12)
$artifactName = "Siyu-AI-Control-Center-$($packageMetadata.version)-$sourceShortSha-windows-x64-setup.exe"
$releasePath = Join-Path $electronPath 'release'
$artifactPath = Join-Path $releasePath $artifactName
$applicationPath = Join-Path $releasePath 'win-unpacked\SiyuAIControlCenter.exe'
$asarPath = Join-Path $releasePath 'win-unpacked\resources\app.asar'

Push-Location $electronPath
try {
    # V1 is intentionally unsigned until a managed Authenticode identity is
    # provisioned. Do not let ambient developer-machine credentials silently
    # change the release status.
    $env:CSC_IDENTITY_AUTO_DISCOVERY = 'false'
    $env:CSC_LINK = ''
    $env:WIN_CSC_LINK = ''
    & pnpm run test
    if ($LASTEXITCODE -ne 0) {
        throw 'Electron 测试失败，已停止发行构建'
    }
    & pnpm exec electron-builder --config electron-builder.config.cjs --win nsis --x64 --publish never
    if ($LASTEXITCODE -ne 0) {
        throw 'Electron Windows 安装包构建失败'
    }
    $fuseOutput = & node (Join-Path $electronPath 'tools\verify-electron-fuses.mjs') $applicationPath
    if ($LASTEXITCODE -ne 0) {
        throw 'Electron Fuse 验证失败'
    }
} finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $artifactPath -PathType Leaf)) {
    throw "未找到预期安装包：$artifactPath"
}
if (-not (Test-Path -LiteralPath $applicationPath -PathType Leaf)) {
    throw "未找到预期应用程序：$applicationPath"
}
if (-not (Test-Path -LiteralPath $asarPath -PathType Leaf)) {
    throw "未找到预期 ASAR：$asarPath"
}

$artifact = Get-Item -LiteralPath $artifactPath
$sha256 = Get-Sha256Hex -LiteralPath $artifactPath
$artifactPe = Get-PeMetadata -LiteralPath $artifactPath
$applicationSha256 = Get-Sha256Hex -LiteralPath $applicationPath
$applicationPe = Get-PeMetadata -LiteralPath $applicationPath
$applicationVersion = [Diagnostics.FileVersionInfo]::GetVersionInfo($applicationPath)
$asarSha256 = Get-Sha256Hex -LiteralPath $asarPath
$fuseVerification = ($fuseOutput -join "`n") | ConvertFrom-Json

if ($applicationPe.Machine -ne 0x8664) {
    throw ('应用程序 PE architecture 不是 x64：0x{0:X4}' -f $applicationPe.Machine)
}
if ($artifactPe.AuthenticodeStatus -ne 'NotSigned' -or $applicationPe.AuthenticodeStatus -ne 'NotSigned') {
    throw 'V1 发行契约要求 installer 与 application 均不包含 Authenticode 证书表'
}

$manifest = [ordered]@{
    product = '思余AI中控台'
    version = [string]$packageMetadata.version
    app_id = 'com.siyu.controlcenter'
    architecture = 'x64'
    source_sha = $sourceSha
    production_url = 'https://119.29.188.118/'
    electron_version = [string]$packageMetadata.devDependencies.electron
    electron_builder_version = [string]$packageMetadata.devDependencies.'electron-builder'
    electron_artifact_sha256 = '26bf9a617d58d81772b3d68305d59ee48272969c15083c06db634a77358a8d9d'
    node_build_version = $nodeVersionText
    package_format = 'nsis_per_user_one_click'
    artifact = $artifact.Name
    artifact_size_bytes = $artifact.Length
    artifact_sha256 = $sha256
    authenticode_status = [string]$artifactPe.AuthenticodeStatus
    application_executable = 'SiyuAIControlCenter.exe'
    application_product_version = [string]$applicationVersion.ProductVersion
    application_architecture = 'x64'
    application_sha256 = $applicationSha256
    application_authenticode_status = [string]$applicationPe.AuthenticodeStatus
    asar_sha256 = $asarSha256
    fuse_version = [string]$fuseVerification.version
    electron_fuses = $fuseVerification.fuses
    auto_update = 'not_configured_manual_installer_upgrade'
    user_data = '%APPDATA%\Siyu AI Control Center'
    built_at_utc = [DateTime]::UtcNow.ToString('o')
}

$utf8WithoutBom = [Text.UTF8Encoding]::new($false)
[IO.File]::WriteAllText(
    (Join-Path $releasePath 'release-manifest.json'),
    (($manifest | ConvertTo-Json -Depth 3) + "`n"),
    $utf8WithoutBom
)
[IO.File]::WriteAllText(
    (Join-Path $releasePath 'SHA256SUMS.txt'),
    "$sha256  $($artifact.Name)`n",
    $utf8WithoutBom
)

$manifest | Format-List
