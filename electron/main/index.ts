import { app, BrowserWindow } from 'electron'

import { registerIpcHandlers } from '../ipc'
import { ManagementLoginService } from '../services'
import { createMainWindow } from './window'

let mainWindow: BrowserWindow | null = null
const managementLoginService = new ManagementLoginService()

app.whenReady().then(() => {
  registerIpcHandlers(managementLoginService)
  mainWindow = createMainWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      mainWindow = createMainWindow()
    }
  })
})

app.on('before-quit', () => {
  void managementLoginService.closeAll()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
