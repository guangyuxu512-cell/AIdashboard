import {
  BrowserWindow,
  ipcMain,
  type IpcMainEvent,
  type IpcMainInvokeEvent,
} from 'electron'

import { isTrustedRendererUrl } from '../config/runtime'
import { setTitleBarTheme } from '../main/window'
import { ManagementLoginService } from '../services'
import { LoginOpeningError } from '../services/management-login-service'
import { randomUUID } from 'node:crypto'
import {
  desktopIpcChannels,
  isDesktopResolvedTheme,
  isManagementLoginCompleteInput,
  isManagementLoginOpenInput,
  isManagementLoginFocusInput,
  isUuid,
} from '../types'

export function registerIpcHandlers(
  managementLoginService: ManagementLoginService,
  trustedRendererOrigin: string,
): void {
  ipcMain.on(desktopIpcChannels.setTitleBarTheme, (event, theme: unknown) => {
    if (!isTrustedIpcSender(event, trustedRendererOrigin)) return
    if (!isDesktopResolvedTheme(theme)) return

    const window = BrowserWindow.fromWebContents(event.sender)
    if (!window) return

    setTitleBarTheme(window, theme)
  })

  ipcMain.handle(
    desktopIpcChannels.focusManagementShop,
    async (event, input: unknown) => {
      assertTrustedIpcSender(event, trustedRendererOrigin)
      if (!isManagementLoginFocusInput(input))
        throw new Error('店铺登录参数无效')
      const parent = BrowserWindow.fromWebContents(event.sender)
      if (!parent) throw new Error('主窗口不存在')
      const correlationId = input.correlationId ?? randomUUID()
      managementLoginService.trace({
        correlationId,
        source: 'ipc',
        phase: 'focus_ipc',
        event: 'start',
      })
      try {
        const focused = await managementLoginService.focusShop(parent, {
          ...input,
          correlationId,
        })
        managementLoginService.trace({
          correlationId,
          source: 'ipc',
          phase: 'focus_ipc',
          event: 'finish',
          focused,
        })
        return focused
      } catch (error) {
        managementLoginService.trace({
          correlationId,
          source: 'ipc',
          phase: 'focus_ipc',
          event: 'error',
          errorCode:
            error instanceof LoginOpeningError ? error.code : 'IPC_ERROR',
        })
        throw error
      }
    },
  )

  ipcMain.handle(
    desktopIpcChannels.openManagementLogin,
    async (event, input: unknown) => {
      assertTrustedIpcSender(event, trustedRendererOrigin)
      if (!isManagementLoginOpenInput(input)) throw new Error('登录参数无效')
      const parent = BrowserWindow.fromWebContents(event.sender)
      if (!parent) throw new Error('主窗口不存在')
      const correlationId =
        input.correlationId ?? input.attemptId ?? randomUUID()
      managementLoginService.trace({
        correlationId,
        source: 'ipc',
        phase: 'open_ipc',
        event: 'start',
      })
      try {
        const result = await managementLoginService.open(parent, {
          ...input,
          correlationId,
        })
        managementLoginService.trace({
          correlationId,
          source: 'ipc',
          phase: 'open_ipc',
          event: 'finish',
        })
        return result
      } catch (error) {
        managementLoginService.trace({
          correlationId,
          source: 'ipc',
          phase: 'open_ipc',
          event: 'error',
          errorCode:
            error instanceof LoginOpeningError ? error.code : 'IPC_ERROR',
        })
        throw error
      }
    },
  )

  ipcMain.handle(
    desktopIpcChannels.refreshManagementLogin,
    (event, attemptId: unknown) => {
      assertTrustedIpcSender(event, trustedRendererOrigin)
      if (!isUuid(attemptId)) throw new Error('登录尝试参数无效')
      return managementLoginService.refresh(attemptId)
    },
  )
  ipcMain.handle(
    desktopIpcChannels.getManagementLoginStatus,
    (event, attemptId: unknown) => {
      assertTrustedIpcSender(event, trustedRendererOrigin)
      if (!isUuid(attemptId)) throw new Error('登录尝试标识无效')
      return managementLoginService.getStatus(attemptId)
    },
  )
  ipcMain.handle(
    desktopIpcChannels.completeManagementLogin,
    (event, input: unknown) => {
      assertTrustedIpcSender(event, trustedRendererOrigin)
      if (!isManagementLoginCompleteInput(input))
        throw new Error('接入参数无效')
      return managementLoginService.complete(input)
    },
  )
  ipcMain.handle(
    desktopIpcChannels.closeManagementLogin,
    async (event, attemptId: unknown) => {
      assertTrustedIpcSender(event, trustedRendererOrigin)
      if (!isUuid(attemptId)) return
      await managementLoginService.close(attemptId)
    },
  )
}

function isTrustedIpcSender(
  event: IpcMainEvent | IpcMainInvokeEvent,
  trustedRendererOrigin: string,
): boolean {
  return (
    event.senderFrame === event.sender.mainFrame &&
    isTrustedRendererUrl(event.senderFrame.url, trustedRendererOrigin)
  )
}

function assertTrustedIpcSender(
  event: IpcMainInvokeEvent,
  trustedRendererOrigin: string,
): void {
  if (!isTrustedIpcSender(event, trustedRendererOrigin)) {
    throw new Error('IPC 来源页面不受信任')
  }
}
