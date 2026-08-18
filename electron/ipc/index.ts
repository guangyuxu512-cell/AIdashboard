import { BrowserWindow, ipcMain } from 'electron'

import { setTitleBarTheme } from '../main/window'
import { desktopIpcChannels, isDesktopResolvedTheme } from '../types'

export function registerIpcHandlers(): void {
  ipcMain.on(desktopIpcChannels.setTitleBarTheme, (event, theme: unknown) => {
    if (!isDesktopResolvedTheme(theme)) return

    const window = BrowserWindow.fromWebContents(event.sender)
    if (!window) return

    setTitleBarTheme(window, theme)
  })
}
