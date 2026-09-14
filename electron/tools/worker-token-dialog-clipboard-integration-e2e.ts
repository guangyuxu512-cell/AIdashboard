import { app, BrowserWindow, clipboard } from 'electron'
import path from 'node:path'

import { createMainWindow } from '../main/window'

const rendererUrl =
  process.env.CONTROL_CENTER_WORKER_TOKEN_RENDERER_URL ??
  'http://127.0.0.1:5173/'
const rendererOrigin = new URL(rendererUrl).origin
const workerTokenProbeText = 'control-center-worker-token-dialog-probe-v1'
const legacyClipboardSentinel = 'control-center-worker-token-legacy-sentinel-v1'
const emulateLegacyDenyPolicy = process.argv.includes(
  '--emulate-legacy-deny-policy',
)

interface InputState {
  dialogVisible: boolean
  type: string | null
  disabled: boolean | null
  readOnly: boolean | null
  selectionComplete: boolean | null
}

interface ButtonTarget {
  x: number
  y: number
}

interface MountResult {
  mounted: boolean
  stage: string
}

app.setName('control-center-worker-token-dialog-probe')
app.setPath(
  'userData',
  path.join(
    app.getPath('temp'),
    `control-center-worker-token-dialog-probe-${process.pid}`,
  ),
)

void app.whenReady().then(async () => {
  let window: BrowserWindow | null = null
  let exitCode = 1
  let phase = 'create integration window'

  try {
    window = createMainWindow({
      rendererUrl,
      trustedRendererOrigin: rendererOrigin,
      allowDevTools: false,
    })
    if (emulateLegacyDenyPolicy) {
      window.webContents.session.setPermissionCheckHandler(() => false)
      window.webContents.session.setPermissionRequestHandler(
        (_webContents, _permission, callback) => callback(false),
      )
    }
    await waitForMainFrameLoad(window)

    phase = 'load Worker Token dialog module'
    await loadWorkerTokenDialogModules(window)
    phase = 'mount Worker Token dialog'
    const mountResult = await mountWorkerTokenDialog(window)
    if (!mountResult.mounted) {
      phase = `mount Worker Token dialog: ${mountResult.stage}`
      throw new Error('Worker Token dialog mount failed')
    }
    await waitForDialogInput(window)
    const maskedInput = await readInputState(window, false)

    if (emulateLegacyDenyPolicy) {
      await clipboard.writeText(legacyClipboardSentinel)
      phase = 'click copy with legacy deny policy'
      await clickButton(window, '复制')
      const fallbackMessageShown = await waitForFallbackMessage(window)
      const dialogAfterFailure = await readInputState(window, false)

      phase = 'show and select token after legacy failure'
      await clickButton(window, '显示')
      const revealedInput = await readInputState(window, true)
      const clipboardStayedNonToken =
        (await clipboard.readText()) !== workerTokenProbeText
      const passed =
        isMasked(maskedInput) &&
        fallbackMessageShown &&
        dialogAfterFailure.dialogVisible &&
        isManualCopyReady(revealedInput) &&
        clipboardStayedNonToken

      await writeResult({
        rendererOrigin,
        policy: 'legacy-unconditional-deny',
        maskedBeforeCopy: isMasked(maskedInput),
        fallbackMessageShown,
        dialogVisibleAfterFailure: dialogAfterFailure.dialogVisible,
        manualSelectionReadyAfterFailure: isManualCopyReady(revealedInput),
        clipboardContainsTokenAfterFailure: !clipboardStayedNonToken,
      })
      exitCode = passed ? 0 : 1
    } else {
      phase = 'show and select token'
      await clickButton(window, '显示')
      const revealedInput = await readInputState(window, true)

      phase = 'click copy and verify clipboard'
      await clickButton(window, '复制')
      const clipboardMatchesToken = await waitForClipboardMatch()
      const passed =
        isMasked(maskedInput) &&
        isManualCopyReady(revealedInput) &&
        clipboardMatchesToken

      await writeResult({
        rendererOrigin,
        policy: 'current',
        maskedBeforeCopy: isMasked(maskedInput),
        manualSelectionReady: isManualCopyReady(revealedInput),
        clipboardMatchesToken,
      })
      exitCode = passed ? 0 : 1
    }
  } catch (error) {
    await writeResult({
      rendererOrigin,
      policy: emulateLegacyDenyPolicy ? 'legacy-unconditional-deny' : 'current',
      probe: 'failed',
      errorType: getErrorType(error),
      phase,
    })
  } finally {
    window?.destroy()
    app.exit(exitCode)
  }
})

async function mountWorkerTokenDialog(
  window: BrowserWindow,
): Promise<MountResult> {
  return (await window.webContents.executeJavaScript(
    `
      (async () => {
        let stage = 'read modules'
        try {
          const { createApp, h, nextTick, ref, NMessageProvider, WorkerTokenDialog } =
            globalThis.__controlCenterWorkerTokenDialogProbeModules
          stage = 'create host'
          if (!document.getElementById('app-overlay-host')) {
            const overlayHost = document.createElement('div')
            overlayHost.id = 'app-overlay-host'
            document.body.append(overlayHost)
          }
          const host = document.createElement('div')
          host.id = 'control-center-worker-token-dialog-probe'
          document.body.append(host)
          stage = 'create app'
          const probeApp = createApp({
            setup() {
              const show = ref(true)
              return () =>
                h(NMessageProvider, null, {
                  default: () =>
                    h(WorkerTokenDialog, {
                      show: show.value,
                      token: ${JSON.stringify(workerTokenProbeText)},
                      'onUpdate:show': (value) => {
                        show.value = value
                      },
                    }),
                })
            },
          })
          stage = 'mount app'
          probeApp.mount(host)
          globalThis.__controlCenterWorkerTokenDialogProbeApp = probeApp
          stage = 'next tick'
          await nextTick()
          return { mounted: true, stage }
        } catch (_error) {
          return { mounted: false, stage }
        }
      })()
    `,
    true,
  )) as MountResult
}

async function loadWorkerTokenDialogModules(
  window: BrowserWindow,
): Promise<void> {
  await window.webContents.executeJavaScript(
    `
      (async () => {
        const [vue, naiveUi, dialogModule] = await Promise.all([
          import('/node_modules/.vite/deps/vue.js'),
          import('/node_modules/.vite/deps/naive-ui.js'),
          import('/src/features/device-management/ui/WorkerTokenDialog.vue'),
        ])
        globalThis.__controlCenterWorkerTokenDialogProbeModules = {
          createApp: vue.createApp,
          h: vue.h,
          nextTick: vue.nextTick,
          ref: vue.ref,
          NMessageProvider: naiveUi.NMessageProvider,
          WorkerTokenDialog: dialogModule.default,
        }
      })()
    `,
    true,
  )
}

async function clickButton(window: BrowserWindow, label: string): Promise<void> {
  const target = (await window.webContents.executeJavaScript(
    `
      (() => {
        const dialog = Array.from(
          document.querySelectorAll('[role="dialog"], .n-modal'),
        ).find((candidate) => candidate.textContent?.includes('Worker Token'))
        const button = Array.from(dialog?.querySelectorAll('button') ?? []).find(
          (candidate) => candidate.textContent?.trim() === ${JSON.stringify(label)},
        )
        if (!button) return null
        const bounds = button.getBoundingClientRect()
        return {
          x: Math.round(bounds.left + bounds.width / 2),
          y: Math.round(bounds.top + bounds.height / 2),
        }
      })()
    `,
    true,
  )) as ButtonTarget | null
  if (!target) throw new Error(`Worker Token dialog button unavailable: ${label}`)

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
  await waitForNextRender()
}

async function readInputState(
  window: BrowserWindow,
  select: boolean,
): Promise<InputState> {
  return (await window.webContents.executeJavaScript(
    `
      (() => {
        const dialog = Array.from(
          document.querySelectorAll('[role="dialog"], .n-modal'),
        ).find((candidate) => candidate.textContent?.includes('Worker Token'))
        const input = dialog?.querySelector('input')
        if (!input) {
          return {
            dialogVisible: Boolean(dialog),
            type: null,
            disabled: null,
            readOnly: null,
            selectionComplete: null,
          }
        }
        if (${JSON.stringify(select)}) {
          input.focus()
          input.select()
        }
        return {
          dialogVisible: true,
          type: input.type,
          disabled: input.disabled,
          readOnly: input.readOnly,
          selectionComplete:
            input.selectionStart === 0 && input.selectionEnd === input.value.length,
        }
      })()
    `,
    true,
  )) as InputState
}

async function waitForDialogInput(window: BrowserWindow): Promise<void> {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const state = await readInputState(window, false)
    if (state.dialogVisible && state.type !== null) return
    await waitForNextRender()
  }
  throw new Error('Worker Token dialog did not render')
}

async function waitForClipboardMatch(): Promise<boolean> {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    if ((await clipboard.readText()) === workerTokenProbeText) return true
    await waitForNextRender()
  }
  return false
}

async function waitForFallbackMessage(window: BrowserWindow): Promise<boolean> {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const messageShown = (await window.webContents.executeJavaScript(
      "document.body.innerText.includes('Worker Token 复制失败，请点击“显示”后手动选中复制')",
      true,
    )) as boolean
    if (messageShown) return true
    await waitForNextRender()
  }
  return false
}

function isMasked(state: InputState): boolean {
  return (
    state.type === 'password' &&
    state.disabled === true &&
    state.readOnly === false
  )
}

function isManualCopyReady(state: InputState): boolean {
  return (
    state.type === 'text' &&
    state.disabled === false &&
    state.readOnly === true &&
    state.selectionComplete === true
  )
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

function waitForNextRender(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 50))
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
