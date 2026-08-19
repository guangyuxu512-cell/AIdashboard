param(
    [ValidateSet('local', 'remote')]
    [string]$Mode = 'local'
)

. (Join-Path $PSScriptRoot 'dev-common.ps1')

$started = New-Object System.Collections.Generic.List[string]
$apiTarget = 'http://127.0.0.1:8000'

try {
    $existingMode = Get-DevMode
    if ($null -ne $existingMode -and [string]$existingMode.mode -ne $Mode) {
        throw "Development environment is already recorded in $($existingMode.mode) mode. Run dev:down before switching modes."
    }
    if ($Mode -eq 'remote' -and $null -eq $existingMode -and (Test-FrontendReal)) {
        throw 'A real-mode Frontend is already running with an unknown API target. Run dev:down before starting remote mode.'
    }

    if ($Mode -eq 'remote') {
        $apiTarget = [Environment]::GetEnvironmentVariable('CONTROL_CENTER_REMOTE_API_URL', 'Process')
        if ([string]::IsNullOrWhiteSpace($apiTarget)) {
            throw 'Remote mode requires CONTROL_CENTER_REMOTE_API_URL to be set to the VPS HTTPS Backend URL.'
        }
        $uri = $null
        if (-not [uri]::TryCreate($apiTarget, [UriKind]::Absolute, [ref]$uri) -or $uri.Scheme -ne 'https') {
            throw 'CONTROL_CENTER_REMOTE_API_URL must be an absolute HTTPS URL.'
        }
        $apiTarget = $uri.AbsoluteUri.TrimEnd('/')
        if (-not (Test-RemoteBackendHealth $apiTarget)) {
            throw 'The VPS Backend HTTPS health check failed.'
        }
        Write-Host 'VPS Backend HTTPS connection verified.'
    }
    elseif ($null -eq (Get-SshTunnelProcess)) {
        Write-Host 'Starting SSH tunnel control-center-dev...'
        Start-DevProcess 'ssh' 'ssh.exe' @('-N', '-T', 'control-center-dev') $script:ProjectRoot | Out-Null
        $started.Add('ssh')
    }
    else {
        Write-Host 'SSH tunnel already running; reusing it.'
    }

    if ($Mode -eq 'local') {
        Wait-DevCondition ${function:Test-PostgreSqlConnection} 15 'PostgreSQL connection failed through the SSH tunnel.'
        Write-Host 'PostgreSQL connection verified.'

        if (-not (Test-BackendHealth)) {
            if ($null -ne (Get-ListenerProcess 8000)) {
                throw 'Port 8000 is occupied but /health is not healthy.'
            }
            Write-Host 'Starting Backend...'
            Start-DevProcess `
                'backend' `
                $script:BackendPython `
                @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000') `
                $script:BackendDirectory | Out-Null
            $started.Add('backend')
            Wait-DevCondition ${function:Test-BackendHealth} 20 'Backend did not become healthy.'
        }
        else {
            Write-Host 'Backend already healthy; reusing it.'
        }
    }

    if (-not (Test-FrontendReal)) {
        if ($null -ne (Get-ListenerProcess 5173)) {
            throw 'Port 5173 is occupied by a server that is not identifiable as Vite real mode.'
        }
        Write-Host 'Starting Frontend in real mode...'
        $pnpm = (Get-Command 'pnpm.cmd').Source
        Start-DevProcess `
            'frontend' `
            $pnpm `
            @('dev:real') `
            $script:FrontendDirectory `
            @{ VITE_API_PROXY_TARGET = $apiTarget } | Out-Null
        $started.Add('frontend')
        Wait-DevCondition ${function:Test-FrontendReal} 20 'Frontend real mode did not become ready.'
    }
    else {
        Write-Host 'Frontend real mode already running; reusing it.'
    }

    if (-not (Test-ElectronRunning)) {
        Write-Host 'Starting Electron...'
        $pnpm = (Get-Command 'pnpm.cmd').Source
        Start-DevProcess 'electron' $pnpm @('dev') $script:ElectronDirectory | Out-Null
        $started.Add('electron')
        Wait-DevCondition ${function:Test-ElectronRunning} 30 'Electron did not start.'
        $electronMainProcess = Get-ElectronMainProcess
        if ($null -eq $electronMainProcess) {
            throw 'Electron main process identity could not be established.'
        }
        Save-ManagedProcess 'electron' $electronMainProcess
    }
    else {
        Write-Host 'Electron already running; reusing it.'
    }

    Save-DevMode $Mode $apiTarget
    Write-Host ''
    & (Join-Path $PSScriptRoot 'dev-status.ps1')
}
catch {
    Write-Error $_
    for ($index = $started.Count - 1; $index -ge 0; $index -= 1) {
        Stop-ManagedProcess $started[$index] | Out-Null
    }
    exit 1
}
