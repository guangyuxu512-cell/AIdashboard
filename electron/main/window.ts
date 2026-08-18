import { BrowserWindow } from 'electron'
import path from 'node:path'

const frontendDevServerUrl = process.env.FRONTEND_DEV_SERVER_URL

export function createMainWindow(): BrowserWindow {
  const window = new BrowserWindow({
    title: '电商 AI 中控台',
    width: 1280,
    height: 800,
    minWidth: 960,
    minHeight: 640,
    autoHideMenuBar: true,
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: path.join(__dirname, '../preload/index.js'),
    },
  })

  window.once('ready-to-show', () => window.show())
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))

  if (frontendDevServerUrl) {
    void window.loadURL(frontendDevServerUrl)
  } else {
    void window.loadFile(path.resolve(__dirname, '../../../frontend/dist/index.html'))
  }

  return window
}
