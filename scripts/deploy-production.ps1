#requires -Version 7.4
[CmdletBinding()]
param(
    [string]$DeploySha,
    [string]$SshHost,
    [string]$PublicHost,
    [ValidateSet('Plan', 'Deploy')][string]$Mode = 'Plan',
    [string]$BackupReference,
    [string]$OutputDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-ProductionCommand {
    param([string]$FilePath, [string[]]$Arguments, [switch]$CaptureOutput)
    if ($CaptureOutput) {
        $commandOutput = & $FilePath @Arguments 2>&1
    }
    else {
        & $FilePath @Arguments | Out-Host
    }
    $commandStatus = $LASTEXITCODE
    if ($commandStatus -ne 0) {
        $failure = [System.Exception]::new("$FilePath failed with exit code $commandStatus.")
        $failure.Data['ExitCode'] = $commandStatus
        throw $failure
    }
    if ($CaptureOutput) { return ($commandOutput -join "`n") }
}

function Assert-ProductionTarget {
    param([string]$RepositoryRoot, [string]$Sha)
    if ($Sha -cnotmatch '^[0-9a-f]{40}$') {
        throw 'Production deployment requires a full lowercase Git commit SHA.'
    }
    Invoke-ProductionCommand git @('-C', $RepositoryRoot, 'fetch', '--no-tags', 'origin', '+refs/heads/main:refs/remotes/origin/main')
    $publishedSha = Invoke-ProductionCommand git @('-C', $RepositoryRoot, 'rev-parse', 'origin/main') -CaptureOutput
    if ($Sha -cne $publishedSha.Trim()) { throw 'Deployment SHA must equal the current origin/main commit.' }
    $origin = Invoke-ProductionCommand git @('-C', $RepositoryRoot, 'remote', 'get-url', 'origin') -CaptureOutput
    if ($origin.Trim() -notmatch '^(?:https://github\.com/|git@github\.com:)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?$') {
        throw 'Production CI must be verified against the GitHub origin repository.'
    }
    $repository = $Matches[1]
    $runsJson = Invoke-ProductionCommand gh @('api', '--hostname', 'github.com', "repos/$repository/actions/workflows/ci.yml/runs?branch=main&event=push&head_sha=$Sha&per_page=100") -CaptureOutput
    $runs = @((ConvertFrom-Json $runsJson).workflow_runs | Where-Object {
        $_.head_sha -ceq $Sha -and $_.head_branch -ceq 'main' -and $_.event -ceq 'push'
    } | Sort-Object -Property id -Descending)
    if ($runs.Count -eq 0 -or $runs[0].status -cne 'completed' -or $runs[0].conclusion -cne 'success') {
        throw 'The latest main push CI for this exact SHA must be completed and successful.'
    }
    return [pscustomobject]@{ Repository = $repository; RunId = $runs[0].id; RunUrl = $runs[0].html_url }
}

function Assert-ProductionHealthBody {
    param([string]$ContentType, [string]$Body)
    if ($ContentType -notmatch '^application/json(?:\s*;|$)') { throw 'Public /health must return application/json.' }
    $health = ConvertFrom-Json -InputObject $Body -AsHashtable
    if ($health.Count -ne 1 -or $health['status'] -cne 'ok') { throw 'Public /health did not return the Backend contract.' }
}

function Invoke-ProductionDeployment {
    param(
        [string]$RepositoryRoot, [string]$Sha, [string]$Target, [string]$PublicAddress,
        [ValidateSet('Plan', 'Deploy')][string]$DeploymentMode = 'Plan',
        [string]$Backup, [string]$ArtifactDirectory
    )
    if ($Target -notmatch '^(?:[A-Za-z0-9_][A-Za-z0-9_.-]*@)?[A-Za-z0-9][A-Za-z0-9_.-]*$') { throw 'Specify a trusted SSH alias or user@host.' }
    if ($PublicAddress -notmatch '^[A-Za-z0-9][A-Za-z0-9.-]*$') { throw 'Specify the public HTTPS host without a scheme or path.' }
    if ($DeploymentMode -eq 'Deploy' -and [string]::IsNullOrWhiteSpace($Backup)) {
        throw 'Deploy requires the Release Gate backup record reference (path, size, SHA-256 and readability evidence).'
    }
    $ci = Assert-ProductionTarget $RepositoryRoot $Sha
    $attempt = 'local-' + [guid]::NewGuid().ToString('N')
    if (-not $ArtifactDirectory) { $ArtifactDirectory = Join-Path $RepositoryRoot ".dev-runtime/production-deploy/$Sha-$attempt" }
    $ArtifactDirectory = [System.IO.Path]::GetFullPath($ArtifactDirectory)
    New-Item -ItemType Directory -Path $ArtifactDirectory -ErrorAction Stop | Out-Null
    $archive = Join-Path $ArtifactDirectory 'release.tar.gz'
    $archivePaths = @(
        '.dockerignore', 'package.json', 'pnpm-lock.yaml', 'pnpm-workspace.yaml',
        'electron/package.json', 'backend', 'frontend', 'mobile', 'deploy/production',
        'scripts/production-env.sh', 'scripts/remote-deploy-production.sh'
    )
    $archiveExclusions = @(':(exclude)**/.env', ':(exclude)**/.env.*')
    Invoke-ProductionCommand git (@('-C', $RepositoryRoot, 'archive', '--format=tar.gz', "--output=$archive", $Sha, '--') + $archivePaths + $archiveExclusions)
    Invoke-ProductionCommand tar @('-xzf', $archive, '-C', $ArtifactDirectory, 'scripts/remote-deploy-production.sh')
    $remoteScript = Join-Path $ArtifactDirectory 'scripts/remote-deploy-production.sh'
    # Both callers must deploy the script contained in the reviewed commit.
    if ((Get-Content -LiteralPath $remoteScript -Raw) -notmatch '(?m)^flock -n 9') {
        throw 'The target release does not contain the shared production deployment lock; complete the reviewed CD transition first.'
    }
    $archiveHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    $remoteRoot = '/opt/ecommerce-control-center/production'
    $remoteArchive = "/tmp/control-center-production-$Sha-$attempt.tar.gz"
    $remoteScriptPath = "/tmp/control-center-production-deploy-$Sha-$attempt.sh"
    $sshOptions = @('-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ServerAliveInterval=30', '-o', 'ServerAliveCountMax=3')
    $receipt = [ordered]@{
        mode = $DeploymentMode; deploy_sha = $Sha; ci_run_id = $ci.RunId; ci_run_url = $ci.RunUrl
        created_at_utc = [DateTimeOffset]::UtcNow.ToString('o'); attempt = $attempt
        archive = $archive; archive_sha256 = $archiveHash; archive_paths = $archivePaths; archive_exclusions = $archiveExclusions
        ssh_target = $Target; public_health = "https://$PublicAddress/health"; backup_reference = $Backup
        result = 'PLAN_ONLY'; server_contacted = $false
    }
    $receiptPath = Join-Path $ArtifactDirectory 'receipt.json'
    $receipt | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $receiptPath -Encoding utf8
    if ($DeploymentMode -eq 'Plan') { return [pscustomobject]$receipt }

    # A saved plan is not deployment authority: re-read main and the latest CI immediately before SSH.
    $latestCi = Assert-ProductionTarget $RepositoryRoot $Sha
    $receipt.ci_run_id = $latestCi.RunId
    $receipt.ci_run_url = $latestCi.RunUrl
    try {
        $receipt.server_contacted = $true
        $currentCommand = "if [ -d '$remoteRoot' ]; then flock -n -E 75 '$remoteRoot/.deploy.lock' sh -c 'readlink -f $remoteRoot/current 2>/dev/null || true'; fi"
        $current = Invoke-ProductionCommand ssh ($sshOptions + @($Target, $currentCommand)) -CaptureOutput
        if ($current.Trim() -ceq "$remoteRoot/releases/$Sha") {
            $receipt.result = 'ALREADY_ACTIVE'
        }
        else {
            Invoke-ProductionCommand ssh ($sshOptions + @($Target, "install -d -m 0750 $remoteRoot"))
            Invoke-ProductionCommand scp ($sshOptions + @($archive, "${Target}:$remoteArchive"))
            Invoke-ProductionCommand scp ($sshOptions + @($remoteScript, "${Target}:$remoteScriptPath"))
            $deployCommand = "printf '%s  %s\n' '$archiveHash' '$remoteArchive' | sha256sum -c - && chmod 0700 '$remoteScriptPath' && '$remoteScriptPath' '$remoteRoot' '$remoteArchive' '$Sha'; status=`$?; rm -f -- '$remoteScriptPath'; exit `$status"
            Invoke-ProductionCommand ssh ($sshOptions + @($Target, $deployCommand))
            $receipt.result = 'DEPLOYED_PENDING_PUBLIC_HEALTH'
        }
        $bodyPath = Join-Path $ArtifactDirectory 'public-health.json'
        $contentType = Invoke-ProductionCommand curl @('--fail', '--silent', '--show-error', '--retry', '3', '--retry-connrefused', '--connect-timeout', '15', '--output', $bodyPath, '--write-out', '%{content_type}', "https://$PublicAddress/health") -CaptureOutput
        Assert-ProductionHealthBody $contentType (Get-Content -LiteralPath $bodyPath -Raw)
        if ($receipt.result -eq 'DEPLOYED_PENDING_PUBLIC_HEALTH') { $receipt.result = 'DEPLOYED' }
        return [pscustomobject]$receipt
    }
    catch {
        $receipt.result = 'FAILED_REQUIRES_SITE_CHECK'
        throw
    }
    finally {
        $receipt | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $receiptPath -Encoding utf8
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    try {
        Invoke-ProductionDeployment -RepositoryRoot (Split-Path -Parent $PSScriptRoot) -Sha $DeploySha -Target $SshHost -PublicAddress $PublicHost -DeploymentMode $Mode -Backup $BackupReference -ArtifactDirectory $OutputDirectory | ConvertTo-Json -Depth 4
    }
    catch {
        Write-Error $_ -ErrorAction Continue
        if ($_.Exception.Data.Contains('ExitCode')) { exit ([int]$_.Exception.Data['ExitCode']) }
        exit 1
    }
}
