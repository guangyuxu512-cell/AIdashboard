import { contextBridge, ipcRenderer } from 'electron'

import type {
  DesktopApi,
  DesktopResolvedTheme,
  ManagementLoginCompleteInput,
  ManagementLoginOpenInput,
  ManagementLoginRefreshResult,
} from '../types'

// Sandboxed preloads cannot load local runtime modules without bundling.
// Keep this whitelist self-contained and mirrored by the formal Main contract.
const setTitleBarThemeChannel = 'appearance:set-title-bar-theme'
const openManagementLoginChannel = 'management-login:open'
const focusManagementShopChannel = 'management-login:focus-shop'
const getManagementLoginStatusChannel = 'management-login:get-status'
const completeManagementLoginChannel = 'management-login:complete'
const refreshManagementLoginChannel = 'management-login:refresh'
const closeManagementLoginChannel = 'management-login:close'
const trustedRendererOrigins = new Set([
  'https://119.29.188.118',
  'http://127.0.0.1:5173',
  'http://127.0.0.1:5180',
])

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
  managementLogin: {
    correlationSupported: true,
    focusShop(input) {
      return ipcRenderer.invoke(focusManagementShopChannel, input)
    },
    open(input: ManagementLoginOpenInput) {
      return ipcRenderer.invoke(openManagementLoginChannel, input)
    },
    getStatus(attemptId: string) {
      return ipcRenderer.invoke(getManagementLoginStatusChannel, attemptId)
    },
    complete(input: ManagementLoginCompleteInput) {
      return ipcRenderer.invoke(completeManagementLoginChannel, input)
    },
    refresh(attemptId: string): Promise<ManagementLoginRefreshResult> {
      return ipcRenderer.invoke(refreshManagementLoginChannel, attemptId)
    },
    close(attemptId: string) {
      return ipcRenderer.invoke(closeManagementLoginChannel, attemptId)
    },
  },
}

if (trustedRendererOrigins.has(window.location.origin)) {
  contextBridge.exposeInMainWorld('desktop', desktopApi)
}
