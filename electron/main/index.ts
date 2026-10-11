import { app, BrowserWindow } from 'electron'

import {
  desktopApplicationId,
  desktopApplicationName,
  resolveDesktopRuntimeConfig,
  resolveDesktopUserDataPath,
} from '../config/runtime'
import { registerIpcHandlers } from '../ipc'
import { ManagementLoginService } from '../services'
import { createMainWindow } from './window'

let mainWindow: BrowserWindow | null = null
const runtimeConfig = resolveDesktopRuntimeConfig({
  isPackaged: app.isPackaged,
})
const managementLoginService = new ManagementLoginService({
  backendBaseUrl: runtimeConfig.backendBaseUrl,
  allowDevTools: !app.isPackaged,
  onDiagnostic: app.isPackaged
    ? undefined
    : (record) =>
        console.info(`[management-login-diagnostic] ${JSON.stringify(record)}`),
})

app.setName(desktopApplicationName)
app.setPath('userData', resolveDesktopUserDataPath(app.getPath('appData')))
app.enableSandbox()
if (process.platform === 'win32') app.setAppUserModelId(desktopApplicationId)

if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  app.on('second-instance', () => focusMainWindow())

  void app.whenReady().then(() => {
    registerIpcHandlers(managementLoginService, runtimeConfig.rendererOrigin)
    mainWindow = openMainWindow()

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        mainWindow = openMainWindow()
      } else {
        focusMainWindow()
      }
    })
  })

  app.on('before-quit', () => {
    void managementLoginService.closeAll()
  })

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit()
  })
}

function openMainWindow(): BrowserWindow {
  const window = createMainWindow({
    rendererUrl: runtimeConfig.rendererUrl,
    trustedRendererOrigin: runtimeConfig.rendererOrigin,
    allowDevTools: !app.isPackaged,
  })
  window.on('closed', () => {
    if (mainWindow === window) {
      mainWindow = null
      // Retained platform windows must not keep the desktop process alive
      // after its main window closes. Cancel pending captures/leases as well.
      void managementLoginService.closeAll()
    }
  })
  return window
}

function focusMainWindow(): void {
  if (!mainWindow || mainWindow.isDestroyed()) return
  if (mainWindow.isMinimized()) mainWindow.restore()
  if (!mainWindow.isVisible()) mainWindow.show()
  mainWindow.focus()
}
