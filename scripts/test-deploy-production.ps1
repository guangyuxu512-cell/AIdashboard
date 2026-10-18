#requires -Version 7.4
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'deploy-production.ps1')
$realCommand = ${function:Invoke-ProductionCommand}
$testRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('production-entry-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot | Out-Null
$script:transportCalls = [System.Collections.Generic.List[string]]::new()
$script:activeRelease = ''
$script:transportFailure = ''
$script:activeVerificationFailed = $false
$script:assertions = 0

function Assert-Test([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw "Assertion failed: $Message" }
    $script:assertions++
}
function Assert-Rejected([scriptblock]$Action, [string]$Message) {
    $rejected = $false
    try { & $Action | Out-Null } catch { $rejected = $true }
    Assert-Test $rejected $Message
}
function Invoke-ProductionCommand {
    param([string]$FilePath, [string[]]$Arguments, [switch]$CaptureOutput)
    if ($FilePath -eq 'git' -and ($Arguments -join ' ') -match 'remote get-url origin$') { return 'https://github.com/fixture/control-center.git' }
    if ($FilePath -eq 'gh') {
        Assert-Test (($Arguments -join ' ') -match "actions/workflows/ci.yml/runs\?branch=main&event=push&head_sha=$script:sha&per_page=100") 'CI is the official workflow, exact main push SHA'
        return (@{ workflow_runs = $script:ciRuns } | ConvertTo-Json -Depth 5)
    }
    if ($FilePath -in @('ssh', 'scp', 'curl')) {
        $script:transportCalls.Add("$FilePath $($Arguments -join ' ')")
        if ($FilePath -in @('ssh', 'scp')) {
            Assert-Test (($Arguments -join ' ') -match 'StrictHostKeyChecking=yes.*ServerAliveInterval=30.*ServerAliveCountMax=3') 'strict host key and keepalive preserved'
        }
        if ($script:transportFailure -eq $FilePath -and ($FilePath -ne 'ssh' -or ($Arguments -join ' ') -match 'sha256sum')) {
            $failure = [System.Exception]::new('simulated transport failure')
            $failure.Data['ExitCode'] = 43
            throw $failure
        }
        if ($FilePath -eq 'ssh' -and $Arguments[-1] -match 'readlink -f ') {
            if ($script:activeVerificationFailed) { throw 'simulated mixed or unhealthy active containers' }
            return $script:activeRelease
        }
        if ($FilePath -eq 'curl') {
            $bodyIndex = [array]::IndexOf($Arguments, '--output') + 1
            '{"status":"ok"}' | Set-Content -LiteralPath $Arguments[$bodyIndex]
            return 'application/json'
        }
        return
    }
    & $realCommand -FilePath $FilePath -Arguments $Arguments -CaptureOutput:$CaptureOutput
}

try {
    $origin = Join-Path $testRoot 'origin.git'
    $repository = Join-Path $testRoot 'repository'
    & $realCommand git @('init', '--bare', $origin) -CaptureOutput | Out-Null
    & $realCommand git @('clone', $origin, $repository) -CaptureOutput | Out-Null
    & $realCommand git @('-C', $repository, 'config', 'user.name', 'production entry test')
    & $realCommand git @('-C', $repository, 'config', 'user.email', 'production-entry@example.invalid')
    foreach ($directory in @('electron', 'backend', 'frontend', 'mobile', 'deploy/production', 'scripts')) {
        New-Item -ItemType Directory -Path (Join-Path $repository $directory) | Out-Null
    }
    foreach ($file in @('.dockerignore', 'package.json', 'pnpm-lock.yaml', 'pnpm-workspace.yaml', 'electron/package.json', 'backend/value.txt', 'frontend/value.txt', 'mobile/value.txt', 'deploy/production/value.txt', 'scripts/production-env.sh')) {
        'committed-byte-content' | Set-Content -LiteralPath (Join-Path $repository $file)
    }
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'remote-deploy-production.sh') -Destination (Join-Path $repository 'scripts/remote-deploy-production.sh')
    Copy-Item -LiteralPath (Join-Path (Split-Path $PSScriptRoot) 'deploy/production/verify-active-release.sh') -Destination (Join-Path $repository 'deploy/production/verify-active-release.sh')
    'fixture-placeholder-not-a-secret' | Set-Content -LiteralPath (Join-Path $repository 'backend/.env.example')
    & $realCommand git @('-C', $repository, 'add', '.')
    & $realCommand git @('-C', $repository, 'commit', '-m', 'reviewed fixture') -CaptureOutput | Out-Null
    & $realCommand git @('-C', $repository, 'branch', '-M', 'main')
    & $realCommand git @('-C', $repository, 'push', 'origin', 'main') -CaptureOutput | Out-Null
    $script:sha = (& $realCommand git @('-C', $repository, 'rev-parse', 'HEAD') -CaptureOutput).Trim()
    $success = @{ id = 20; head_sha = $script:sha; head_branch = 'main'; event = 'push'; status = 'completed'; conclusion = 'success'; html_url = 'https://github.com/fixture/control-center/actions/runs/20' }
    $script:ciRuns = @($success)
    $deployArguments = @{ RepositoryRoot = $repository; Sha = $script:sha; Target = 'fixture-production'; PublicAddress = 'production.example.invalid' }
    'uncommitted-changed-bytes' | Set-Content -LiteralPath (Join-Path $repository 'backend/value.txt')
    'fixture-secret-must-not-be-uploaded' | Set-Content -LiteralPath (Join-Path $repository 'backend/.env')
    'untracked-must-not-be-uploaded' | Set-Content -LiteralPath (Join-Path $repository 'backend/untracked.txt')

    $plan = Invoke-ProductionDeployment @deployArguments
    Assert-Test ($plan.result -eq 'PLAN_ONLY' -and -not $plan.server_contacted -and $script:transportCalls.Count -eq 0) 'default Plan does not contact any server or health endpoint'
    $entries = & $realCommand tar @('-tzf', $plan.archive) -CaptureOutput
    Assert-Test ($entries -notmatch '/\.env(?:\.|\r?\n|$)|untracked\.txt') 'all environment files and untracked worktree files excluded'
    $bytes = & $realCommand tar @('-xOzf', $plan.archive, 'backend/value.txt') -CaptureOutput
    Assert-Test ($bytes.Trim() -eq 'committed-byte-content') 'archive contains exact committed bytes, not dirty worktree'
    $scriptBlob = (& $realCommand git @('-C', $repository, 'rev-parse', "$script:sha`:scripts/remote-deploy-production.sh") -CaptureOutput).Trim()
    $extractedBlob = (& $realCommand git @('-C', $repository, 'hash-object', (Join-Path (Split-Path $plan.archive) 'scripts/remote-deploy-production.sh')) -CaptureOutput).Trim()
    Assert-Test ($scriptBlob -ceq $extractedBlob) 'uploaded script is also extracted from the exact commit'

    foreach ($state in @('failure', 'cancelled', 'in_progress', 'missing')) {
        $latest = $success.Clone(); $latest.id = 21; $latest.conclusion = $state
        if ($state -eq 'in_progress') { $latest.status = 'in_progress'; $latest.conclusion = $null }
        $script:ciRuns = if ($state -eq 'missing') { @() } else { @($success, $latest) }
        Assert-Rejected { Invoke-ProductionDeployment @deployArguments } "latest CI $state rejected even if an older run succeeded"
    }
    $script:ciRuns = @($success)
    Assert-Rejected { Invoke-ProductionDeployment @deployArguments -DeploymentMode Deploy } 'Deploy requires the existing verified backup record reference'
    Assert-Rejected { Assert-ProductionTarget $repository ('A' * 40) } 'uppercase SHA rejected'
    Assert-Rejected { Assert-ProductionTarget $repository ('0' * 40) } 'stale SHA rejected'
    Assert-Rejected { Invoke-ProductionDeployment -RepositoryRoot $repository -Sha $script:sha -Target '-option@host' -PublicAddress 'production.example.invalid' } 'option-like SSH user rejected'
    Assert-Rejected { Assert-ProductionHealthBody 'text/html' '<html>ok</html>' } 'HTML is not a health success'
    Assert-Rejected { Assert-ProductionHealthBody 'application/json' '{"status":"ok","extra":true}' } 'health requires exact Backend JSON'
    Assert-ProductionHealthBody 'application/json; charset=utf-8' '{"status":"ok"}'

    $script:transportCalls.Clear()
    $deployed = Invoke-ProductionDeployment @deployArguments -DeploymentMode Deploy -Backup 'fixture existing Release Gate backup record'
    Assert-Test ($deployed.result -eq 'DEPLOYED') 'shared entry executes complete transport and public health sequence'
    Assert-Test (@($script:transportCalls | Where-Object { $_ -match '^scp ' }).Count -eq 2) 'source archive and reviewed remote script are uploaded'
    Assert-Test (($script:transportCalls -join "`n") -match 'sha256sum -c -.*status=\$\?; rm -f .*exit \$status') 'archive hash and remote exit code are retained'

    $script:transportCalls.Clear()
    $script:activeRelease = "/opt/ecommerce-control-center/production/releases/$script:sha"
    $skipped = Invoke-ProductionDeployment @deployArguments -DeploymentMode Deploy -Backup 'fixture backup record'
    Assert-Test ($skipped.result -eq 'ALREADY_ACTIVE') 'same active SHA skips deployment'
    Assert-Test (($script:transportCalls -join "`n") -match 'flock -n -E 75.*readlink -f') 'active-SHA precheck uses the same host lock'
    Assert-Test (($script:transportCalls -join "`n") -match 'verify-active-release.sh.*\|\| exit \$\?') 'active-SHA verification fails closed before any success result'
    Assert-Test (@($script:transportCalls | Where-Object { $_ -match '^scp |sha256sum|install -d' }).Count -eq 0) 'same SHA does not upload or mutate the server'
    $script:transportCalls.Clear()
    $script:activeVerificationFailed = $true
    $failedDirectory = Join-Path $testRoot 'failed-active-state'
    Assert-Rejected { Invoke-ProductionDeployment @deployArguments -DeploymentMode Deploy -Backup 'fixture backup record' -ArtifactDirectory $failedDirectory } 'current-only or mixed/unhealthy runtime never reports ALREADY_ACTIVE'
    $failedReceipt = Get-Content -LiteralPath (Join-Path $failedDirectory 'receipt.json') -Raw | ConvertFrom-Json
    Assert-Test ($failedReceipt.result -eq 'FAILED_REQUIRES_SITE_CHECK') 'active verification failure is recorded for site inspection'
    Assert-Test (@($script:transportCalls | Where-Object { $_ -match '^scp |sha256sum|install -d|^curl ' }).Count -eq 0) 'invalid active state causes no upload, rebuild or misleading generic-health success'
    $script:activeVerificationFailed = $false
    $script:activeRelease = ''

    foreach ($transport in @('scp', 'ssh')) {
        $script:transportFailure = $transport
        $preserved = $false
        try { Invoke-ProductionDeployment @deployArguments -DeploymentMode Deploy -Backup 'fixture backup record' | Out-Null }
        catch { $preserved = $_.Exception.Data['ExitCode'] -eq 43 }
        Assert-Test $preserved "$transport nonzero exit is preserved and never reported as success"
    }
    $script:transportFailure = ''
    $preserved = $false
    try { & $realCommand pwsh @('-NoProfile', '-Command', 'exit 41') }
    catch { $preserved = $_.Exception.Data['ExitCode'] -eq 41 }
    Assert-Test $preserved 'real native process exit code is attached to the CLI error'
    Write-Host "Production local entry regressions passed ($script:assertions assertions; GitHub and server transports simulated)."
}
finally {
    $resolvedRoot = [System.IO.Path]::GetFullPath($testRoot)
    $resolvedTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if (-not $resolvedRoot.StartsWith($resolvedTemp, [System.StringComparison]::OrdinalIgnoreCase) -or (Split-Path $resolvedRoot -Leaf) -notlike 'production-entry-*') { throw 'Unsafe test cleanup target.' }
    Remove-Item -LiteralPath $resolvedRoot -Recurse -Force
}
