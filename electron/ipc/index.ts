import { BrowserWindow, ipcMain } from 'electron'

import { setTitleBarTheme } from '../main/window'
import { ManagementLoginService } from '../services'
import {
  desktopIpcChannels,
  isDesktopResolvedTheme,
  isManagementLoginCompleteInput,
  isManagementLoginOpenInput,
  isUuid,
} from '../types'

export function registerIpcHandlers(
  managementLoginService: ManagementLoginService,
): void {
  ipcMain.on(desktopIpcChannels.setTitleBarTheme, (event, theme: unknown) => {
    if (!isDesktopResolvedTheme(theme)) return

    const window = BrowserWindow.fromWebContents(event.sender)
    if (!window) return

    setTitleBarTheme(window, theme)
  })

  ipcMain.handle(
    desktopIpcChannels.openManagementLogin,
    async (event, input: unknown) => {
      if (!isManagementLoginOpenInput(input)) throw new Error('登录参数无效')
      const parent = BrowserWindow.fromWebContents(event.sender)
      if (!parent) throw new Error('主窗口不存在')
      return managementLoginService.open(parent, input)
    },
  )
  ipcMain.handle(
    desktopIpcChannels.getManagementLoginStatus,
    (_event, attemptId: unknown) => {
      if (!isUuid(attemptId)) throw new Error('登录尝试标识无效')
      return managementLoginService.getStatus(attemptId)
    },
  )
  ipcMain.handle(
    desktopIpcChannels.completeManagementLogin,
    (_event, input: unknown) => {
      if (!isManagementLoginCompleteInput(input)) throw new Error('接入参数无效')
      return managementLoginService.complete(input)
    },
  )
  ipcMain.handle(
    desktopIpcChannels.closeManagementLogin,
    async (_event, attemptId: unknown) => {
      if (!isUuid(attemptId)) return
      await managementLoginService.close(attemptId)
    },
  )
}
