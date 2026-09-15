import { createServer, type Server } from 'node:http'
import path from 'node:path'

import { app, BrowserWindow, clipboard } from 'electron'

import { createMainWindow } from '../main/window'

const integrationRendererUrl = 'http://127.0.0.1:5180/'
const integrationRendererOrigin = 'http://127.0.0.1:5180'
const clipboardProbeText = 'control-center-worker-token-copy-probe-v1'
const untrustedClipboardProbeText =
  'control-center-worker-token-copy-untrusted-probe-v1'
const emulateLegacyDenyPolicy = process.argv.includes(
  '--emulate-legacy-deny-policy',
)

interface ClipboardProbeResult {
  outcome: 'written' | 'rejected'
  errorType: string | null
}

interface UntrustedProbeServer {
  server: Server
  url: string
}

type ClipboardProbeTrigger = 'mouse-input' | 'dom-click'

app.setName('control-center-clipboard-permission-probe')
app.setPath(
  'userData',
  path.join(
    app.getPath('temp'),
    `control-center-clipboard-probe-${process.pid}`,
  ),
)

void app.whenReady().then(async () => {
  let mainWindow: BrowserWindow | null = null
  let untrustedWindow: BrowserWindow | null = null
  let untrustedServer: UntrustedProbeServer | null = null
  let exitCode = 1
  let phase = 'create trusted window'

  try {
    mainWindow = createMainWindow({
      rendererUrl: integrationRendererUrl,
      trustedRendererOrigin: integrationRendererOrigin,
      allowDevTools: false,
    })
    if (emulateLegacyDenyPolicy) {
      mainWindow.webContents.session.setPermissionCheckHandler(() => false)
      mainWindow.webContents.session.setPermissionRequestHandler(
        (_webContents, _permission, callback) => callback(false),
      )
    }
    await waitForMainFrameLoad(mainWindow)

    phase = 'trusted clipboard click'
    const trustedResult = await clickClipboardProbe(
      mainWindow,
      clipboardProbeText,
      'mouse-input',
    )
    const clipboardMatchesProbe =
      trustedResult.outcome === 'written' &&
      (await clipboard.readText()) === clipboardProbeText

    phase = 'start untrusted renderer'
    untrustedServer = await createUntrustedProbeServer()
    untrustedWindow = new BrowserWindow({
      show: true,
      webPreferences: {
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
        webSecurity: true,
        allowRunningInsecureContent: false,
        webviewTag: false,
      },
    })
    await untrustedWindow.loadURL(untrustedServer.url)
    untrustedWindow.focus()
    phase = 'untrusted clipboard click'
    const untrustedResult = await clickClipboardProbe(
      untrustedWindow,
      untrustedClipboardProbeText,
      'dom-click',
    )

    const passed = emulateLegacyDenyPolicy
      ? trustedResult.outcome === 'rejected' &&
        !clipboardMatchesProbe &&
        untrustedResult.outcome === 'rejected'
      : trustedResult.outcome === 'written' &&
        clipboardMatchesProbe &&
        untrustedResult.outcome === 'rejected'
    phase = 'record result'
    await writeResult({
      rendererOrigin: integrationRendererOrigin,
      policy: emulateLegacyDenyPolicy ? 'legacy-unconditional-deny' : 'current',
      trustedClipboardWrite: trustedResult.outcome,
      trustedErrorType: trustedResult.errorType,
      trustedClipboardMatchesProbe: clipboardMatchesProbe,
      untrustedRendererOrigin: untrustedServer.url,
      untrustedTrigger: 'dom-click',
      untrustedClipboardWrite: untrustedResult.outcome,
      untrustedErrorType: untrustedResult.errorType,
    })
    exitCode = passed ? 0 : 1
  } catch (error) {
    await writeResult({
      rendererOrigin: integrationRendererOrigin,
      policy: emulateLegacyDenyPolicy ? 'legacy-unconditional-deny' : 'current',
      clipboardWrite: 'probe-failed',
      errorType: getErrorType(error),
      phase,
    })
  } finally {
    untrustedWindow?.destroy()
    mainWindow?.destroy()
    if (untrustedServer) await closeServer(untrustedServer.server)
    app.exit(exitCode)
  }
})

async function clickClipboardProbe(
  window: BrowserWindow,
  probeText: string,
  trigger: ClipboardProbeTrigger,
): Promise<ClipboardProbeResult> {
  const target = (await window.webContents.executeJavaScript(
    `
      (() => {
        const button = document.createElement('button')
        button.id = 'control-center-clipboard-permission-probe'
        button.textContent = 'Clipboard permission probe'
        button.style.cssText = 'position: fixed; top: 24px; left: 24px; z-index: 2147483647'
        button.addEventListener('click', async () => {
          try {
            await navigator.clipboard.writeText(${JSON.stringify(probeText)})
            globalThis.__controlCenterClipboardProbeResult = {
              outcome: 'written',
              errorType: null,
            }
          } catch (error) {
            globalThis.__controlCenterClipboardProbeResult = {
              outcome: 'rejected',
              errorType:
                error && typeof error === 'object' && typeof error.name === 'string'
                  ? error.name
                  : typeof error,
            }
          }
        })
        document.body.append(button)
        const bounds = button.getBoundingClientRect()
        return {
          x: Math.round(bounds.left + bounds.width / 2),
          y: Math.round(bounds.top + bounds.height / 2),
        }
      })()
    `,
    true,
  )) as { x: number; y: number }
  if (trigger === 'mouse-input') {
    window.webContents.sendInputEvent({
      type: 'mouseDown',
      x: target.x,
      y: target.y,
      button: 'left',
      clickCount: 1,
    })
    window.webContents.sendInputEvent({
      type: 'mouseUp',
      x: target.x,
      y: target.y,
      button: 'left',
      clickCount: 1,
    })
  } else {
    await window.webContents.executeJavaScript(
      "document.querySelector('#control-center-clipboard-permission-probe')?.click()",
      true,
    )
  }
  return waitForClipboardProbeResult(window)
}

function createUntrustedProbeServer(): Promise<UntrustedProbeServer> {
  return new Promise((resolve, reject) => {
    const server = createServer((_request, response) => {
      response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' })
      response.end('<!doctype html><title>Untrusted clipboard probe</title>')
    })
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const address = server.address()
      if (!address || typeof address === 'string') {
        reject(new Error('Untrusted probe server did not expose a TCP port'))
        return
      }
      resolve({ server, url: `http://127.0.0.1:${address.port}/` })
    })
  })
}

function closeServer(server: Server): Promise<void> {
  return new Promise((resolve, reject) => {
    server.close((error) => (error ? reject(error) : resolve()))
  })
}

function waitForMainFrameLoad(window: BrowserWindow): Promise<void> {
  return new Promise((resolve, reject) => {
    window.webContents.once('did-finish-load', () => resolve())
    window.webContents.once(
      'did-fail-load',
      (_event, errorCode, _description, _validatedUrl, isMainFrame) => {
        if (isMainFrame) {
          reject(new Error(`Integration Renderer load failed: ${errorCode}`))
        }
      },
    )
  })
}

async function waitForClipboardProbeResult(
  window: BrowserWindow,
): Promise<ClipboardProbeResult> {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const result = (await window.webContents.executeJavaScript(
      'globalThis.__controlCenterClipboardProbeResult ?? null',
      true,
    )) as ClipboardProbeResult | null
    if (result) return result
    await new Promise((resolve) => setTimeout(resolve, 50))
  }
  throw new Error('Clipboard probe click did not complete')
}

function getErrorType(error: unknown): string {
  if (
    error &&
    typeof error === 'object' &&
    'name' in error &&
    typeof error.name === 'string'
  ) {
    return error.name
  }
  return typeof error
}

function writeResult(result: Record<string, unknown>): Promise<void> {
  return new Promise((resolve, reject) => {
    process.stdout.write(`${JSON.stringify(result)}\n`, (error) => {
      if (error) reject(error)
      else resolve()
    })
  })
}
