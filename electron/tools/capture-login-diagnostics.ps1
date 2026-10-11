[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$LaunchScript
)

$ErrorActionPreference = 'Stop'
$repoRoot = (& git -C $PSScriptRoot rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0) { throw '无法确认当前工作树' }
$localRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot '.codex'))
$entry = (Resolve-Path -LiteralPath $LaunchScript -ErrorAction Stop).Path
if (-not $entry.StartsWith($localRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or
    [IO.Path]::GetExtension($entry) -ne '.ps1') {
    throw '仅允许调用本工作树 .codex 中已准备的正常开发启动入口'
}

$existing = @(Get-Process -Name electron -ErrorAction SilentlyContinue)
if ($existing.Count -gt 0) {
    throw '请先正常退出已有开发 Electron；本入口不会结束进程或启动第二实例'
}
if ($env:ELECTRON_LOG_FILE) {
    throw '检测到旧的原始 Electron 日志配置；请先移除，再使用白名单诊断入口'
}

$logRoot = Join-Path $localRoot 'shop-login-session-sync'
$logPath = Join-Path $logRoot ('main-diagnostic-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff') + '.jsonl')
& git -C $repoRoot check-ignore -- $logPath | Out-Null
if ($LASTEXITCODE -ne 0) { throw '诊断目标未被 Git 忽略，停止启动' }
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
New-Item -ItemType File -Path $logPath -ErrorAction Stop | Out-Null
$utf8 = [Text.UTF8Encoding]::new($false)
$prefix = '[management-login-diagnostic] '
$phases = @('open', 'load', 'detect', 'capture', 'refresh', 'close')
$events = @('start', 'finish', 'error', 'redirect', 'request', 'closed', 'renderer_gone')
$reasons = @('renderer_request', 'load_failed', 'app_shutdown', 'attempt_timeout', 'onboarding_capture', 'completed_onboarding', 'window_closed_without_request')

Write-Host '仅保存白名单阶段诊断；不保存原始 stdout/stderr。请保留原有登录会话，无需重新登录。'
Write-Host ('诊断文件：' + $logPath)
# Native stderr may contain a URL. It is handled only in this pipeline, never
# displayed or persisted; records are rebuilt from the narrow schema below.
$ErrorActionPreference = 'Continue'
& $entry *>&1 | ForEach-Object {
    $line = $_.ToString()
    if ($line.StartsWith($prefix, [StringComparison]::Ordinal)) {
        try {
            $record = $line.Substring($prefix.Length) | ConvertFrom-Json -ErrorAction Stop
            $parsedId = [Guid]::Empty
            $parsedTime = [DateTimeOffset]::MinValue
            if (-not [Guid]::TryParse([string]$record.attemptId, [ref]$parsedId) -or
                -not [DateTimeOffset]::TryParse([string]$record.timestamp, [ref]$parsedTime) -or
                $phases -notcontains $record.phase -or $events -notcontains $record.event) {
                return
            }
            $safe = [ordered]@{
                timestamp = $parsedTime.ToUniversalTime().ToString('o')
                attemptId = $parsedId.ToString('D')
                phase = [string]$record.phase
                event = [string]$record.event
                errorCode = $null
                errno = $null
                isMainFrame = $null
                mainFrameLoading = $null
                closeReason = $null
            }
            if ($record.errorCode -is [string] -and $record.errorCode -cmatch '^(?:ERR_[A-Z0-9_]{1,48}|ENOENT|EACCES|ECONNRESET|ETIMEDOUT)$') {
                $safe.errorCode = $record.errorCode
            }
            if (($record.errno -is [int] -or $record.errno -is [long]) -and $record.errno -ge -2147483648 -and $record.errno -le 2147483647) {
                $safe.errno = $record.errno
            }
            if ($record.isMainFrame -is [bool]) { $safe.isMainFrame = $record.isMainFrame }
            if ($record.mainFrameLoading -is [bool]) { $safe.mainFrameLoading = $record.mainFrameLoading }
            if ($reasons -contains $record.closeReason) { $safe.closeReason = [string]$record.closeReason }
            [IO.File]::AppendAllText($logPath, (($safe | ConvertTo-Json -Compress) + [Environment]::NewLine), $utf8)
        } catch {
            # Drop malformed records without logging the original content.
        }
    }
}
Write-Host ('开发 Electron 已退出；白名单诊断文件：' + $logPath)
