import { BrowserWindow, nativeTheme } from 'electron'
import path from 'node:path'

import { isTrustedRendererUrl } from '../config/runtime'
import type { DesktopResolvedTheme } from '../types'

const titleBarHeight = 54
const titleBarSymbolColors: Record<DesktopResolvedTheme, string> = {
  light: '#222a34',
  dark: '#e4e7eb',
}

interface MainWindowOptions {
  rendererUrl: string
  trustedRendererOrigin: string
  allowDevTools: boolean
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

export function createMainWindow(options: MainWindowOptions): BrowserWindow {
  const initialTheme: DesktopResolvedTheme = nativeTheme.shouldUseDarkColors
    ? 'dark'
    : 'light'
  const window = new BrowserWindow({
    title: '思余AI中控台',
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
      webSecurity: true,
      allowRunningInsecureContent: false,
      devTools: options.allowDevTools,
      navigateOnDragDrop: false,
      webviewTag: false,
      preload: path.join(__dirname, '../preload/index.js'),
    },
  })

  window.once('ready-to-show', () => window.show())
  window.webContents.on(
    'did-fail-load',
    (_event, _code, _description, _url, isMainFrame) => {
      if (isMainFrame && !window.isDestroyed()) window.show()
    },
  )
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
  window.webContents.on('will-navigate', (event, navigationUrl) => {
    if (
      !isTrustedRendererUrl(navigationUrl, options.trustedRendererOrigin)
    ) {
      event.preventDefault()
    }
  })
  window.webContents.on('will-redirect', (event, navigationUrl) => {
    if (
      !isTrustedRendererUrl(navigationUrl, options.trustedRendererOrigin)
    ) {
      event.preventDefault()
    }
  })
  window.webContents.session.setPermissionCheckHandler(() => false)
  window.webContents.session.setPermissionRequestHandler(
    (_webContents, _permission, callback) => callback(false),
  )

  void window.loadURL(options.rendererUrl).catch(() => {
    if (!window.isDestroyed()) window.show()
  })

  return window
}
