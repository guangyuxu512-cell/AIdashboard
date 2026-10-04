import { BrowserWindow, nativeTheme } from 'electron'
import path from 'node:path'
import os from 'node:os'

import { isTrustedRendererUrl } from '../config/runtime'
import {
  desktopIpcChannels,
  type DesktopResolvedTheme,
  type DesktopWindowState,
} from '../types'
import { installMainWindowPermissionHandlers } from './permissions'
import { needsWindowsRegion, roundedWindowRegion } from './window-shape'

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
          roundedCorners: true,
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

  const needsRegion = needsWindowsRegion(process.platform, os.release())
  const synchronizeWindowShape = () => {
    if (window.isDestroyed()) return
    const state: DesktopWindowState = window.isFullScreen()
      ? 'fullscreen'
      : window.isMaximized()
        ? 'maximized'
        : 'normal'
    if (needsRegion) {
      const { width, height } = window.getBounds()
      window.setShape(
        state === 'normal' ? roundedWindowRegion(width, height) : [],
      )
    }
    window.webContents.send(desktopIpcChannels.windowState, state)
  }
  window.on('resize', synchronizeWindowShape)
  window.on('maximize', synchronizeWindowShape)
  window.on('unmaximize', synchronizeWindowShape)
  window.on('enter-full-screen', synchronizeWindowShape)
  window.on('leave-full-screen', synchronizeWindowShape)
  window.on('restore', synchronizeWindowShape)
  window.webContents.on('did-finish-load', synchronizeWindowShape)
  synchronizeWindowShape()

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
  installMainWindowPermissionHandlers(
    window.webContents,
    options.trustedRendererOrigin,
  )

  void window.loadURL(options.rendererUrl).catch(() => {
    if (!window.isDestroyed()) window.show()
  })

  return window
}
