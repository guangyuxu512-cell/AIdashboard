import { contextBridge, ipcRenderer } from 'electron'

import type { DesktopApi, DesktopResolvedTheme } from '../types'

// Sandboxed preloads cannot load local runtime modules without bundling.
// Keep this whitelist self-contained and mirrored by the formal Main contract.
const setTitleBarThemeChannel = 'appearance:set-title-bar-theme'

function isDesktopResolvedTheme(value: unknown): value is DesktopResolvedTheme {
  return value === 'light' || value === 'dark'
}

const desktopApi: DesktopApi = {
  appearance: {
    setTitleBarTheme(theme) {
      if (!isDesktopResolvedTheme(theme)) return
      ipcRenderer.send(setTitleBarThemeChannel, theme)
    },
  },
}

contextBridge.exposeInMainWorld('desktop', desktopApi)
