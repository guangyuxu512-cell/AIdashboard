import { BrowserWindow, nativeTheme } from 'electron'
import path from 'node:path'

import type { DesktopResolvedTheme } from '../types'

const frontendDevServerUrl = process.env.FRONTEND_DEV_SERVER_URL
const titleBarHeight = 54
const titleBarSymbolColors: Record<DesktopResolvedTheme, string> = {
  light: '#222a34',
  dark: '#e4e7eb',
}

export function setTitleBarTheme(
  window: BrowserWindow,
  theme: DesktopResolvedTheme,
): void {
  if (process.platform !== 'win32' || window.isDestroyed()) return

  window.setTitleBarOverlay({
    color: '#00000000',
    symbolColor: titleBarSymbolColors[theme],
    height: titleBarHeight,
  })
}

export function createMainWindow(): BrowserWindow {
  const initialTheme: DesktopResolvedTheme = nativeTheme.shouldUseDarkColors
    ? 'dark'
    : 'light'
  const window = new BrowserWindow({
    title: '电商 AI 中控台',
    width: 1280,
    height: 800,
    minWidth: 960,
    minHeight: 640,
    autoHideMenuBar: true,
    show: false,
    ...(process.platform === 'win32'
      ? {
          titleBarStyle: 'hidden' as const,
          titleBarOverlay: {
            color: '#00000000',
            symbolColor: titleBarSymbolColors[initialTheme],
            height: titleBarHeight,
          },
        }
      : {}),
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
    void window.loadFile(
      path.resolve(__dirname, '../../../frontend/dist/index.html'),
    )
  }

  return window
}
