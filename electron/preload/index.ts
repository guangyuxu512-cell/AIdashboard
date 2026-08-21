import { contextBridge, ipcRenderer } from 'electron'

import type {
  DesktopApi,
  DesktopResolvedTheme,
  ManagementLoginCompleteInput,
  ManagementLoginOpenInput,
} from '../types'

// Sandboxed preloads cannot load local runtime modules without bundling.
// Keep this whitelist self-contained and mirrored by the formal Main contract.
const setTitleBarThemeChannel = 'appearance:set-title-bar-theme'
const openManagementLoginChannel = 'management-login:open'
const getManagementLoginStatusChannel = 'management-login:get-status'
const completeManagementLoginChannel = 'management-login:complete'
const closeManagementLoginChannel = 'management-login:close'

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
    open(input: ManagementLoginOpenInput) {
      return ipcRenderer.invoke(openManagementLoginChannel, input)
    },
    getStatus(attemptId: string) {
      return ipcRenderer.invoke(getManagementLoginStatusChannel, attemptId)
    },
    complete(input: ManagementLoginCompleteInput) {
      return ipcRenderer.invoke(completeManagementLoginChannel, input)
    },
    close(attemptId: string) {
      return ipcRenderer.invoke(closeManagementLoginChannel, attemptId)
    },
  },
}

contextBridge.exposeInMainWorld('desktop', desktopApi)
