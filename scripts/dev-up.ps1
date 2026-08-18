. (Join-Path $PSScriptRoot 'dev-common.ps1')

$started = New-Object System.Collections.Generic.List[string]

try {
    if ($null -eq (Get-SshTunnelProcess)) {
        Write-Host 'Starting SSH tunnel control-center-dev...'
        Start-DevProcess 'ssh' 'ssh.exe' @('-N', '-T', 'control-center-dev') $script:ProjectRoot | Out-Null
        $started.Add('ssh')
    }
    else {
        Write-Host 'SSH tunnel already running; reusing it.'
    }

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

    if (-not (Test-FrontendReal)) {
        if ($null -ne (Get-ListenerProcess 5173)) {
            throw 'Port 5173 is occupied by a server that is not identifiable as Vite real mode.'
        }
        Write-Host 'Starting Frontend in real mode...'
        $pnpm = (Get-Command 'pnpm.cmd').Source
        Start-DevProcess 'frontend' $pnpm @('dev:real') $script:FrontendDirectory | Out-Null
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
