import { app, BrowserWindow } from 'electron'

import { registerIpcHandlers } from '../ipc'
import { createMainWindow } from './window'

let mainWindow: BrowserWindow | null = null

app.whenReady().then(() => {
  registerIpcHandlers()
  mainWindow = createMainWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      mainWindow = createMainWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
