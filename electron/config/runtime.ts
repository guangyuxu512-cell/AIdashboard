import path from 'node:path'

export const desktopApplicationId = 'com.siyu.controlcenter'
export const desktopApplicationName = '思余AI中控台'
export const desktopUserDataDirectoryName = 'Siyu AI Control Center'
export const productionConsoleOrigin = 'https://119.29.188.118'
export const productionConsoleUrl = `${productionConsoleOrigin}/`

const defaultDevelopmentFrontendUrl = 'http://127.0.0.1:5173/'
const defaultDevelopmentBackendUrl = 'http://127.0.0.1:8000/'
const trustedDevelopmentFrontendOrigins = new Set([
  'http://127.0.0.1:5173',
  'http://127.0.0.1:5180',
])

export interface DesktopRuntimeConfig {
  rendererUrl: string
  rendererOrigin: string
  backendBaseUrl: string
}

export function resolveDesktopRuntimeConfig(input: {
  isPackaged: boolean
  environment?: NodeJS.ProcessEnv
}): DesktopRuntimeConfig {
  if (input.isPackaged) {
    return {
      rendererUrl: productionConsoleUrl,
      rendererOrigin: productionConsoleOrigin,
      backendBaseUrl: productionConsoleUrl,
    }
  }

  const environment = input.environment ?? process.env
  const rendererUrl = normalizeDevelopmentRendererUrl(
    environment.FRONTEND_DEV_SERVER_URL ?? defaultDevelopmentFrontendUrl,
  )
  return {
    rendererUrl,
    rendererOrigin: new URL(rendererUrl).origin,
    backendBaseUrl: normalizeBackendBaseUrl(
      environment.CONTROL_CENTER_BACKEND_URL ??
        defaultDevelopmentBackendUrl,
    ),
  }
}

export function resolveDesktopUserDataPath(appDataPath: string): string {
  if (!path.isAbsolute(appDataPath)) {
    throw new Error('Electron appData 路径必须是绝对路径')
  }
  return path.join(appDataPath, desktopUserDataDirectoryName)
}

export function isTrustedRendererUrl(
  value: string,
  trustedOrigin: string,
): boolean {
  try {
    const url = new URL(value)
    return (
      !url.username &&
      !url.password &&
      url.origin === trustedOrigin &&
      (url.protocol === 'https:' || isLoopbackHttpUrl(url))
    )
  } catch {
    return false
  }
}

function normalizeDevelopmentRendererUrl(value: string): string {
  const url = parseRootUrl(value, 'Electron 开发前端地址')
  if (!trustedDevelopmentFrontendOrigins.has(url.origin)) {
    throw new Error('Electron 开发前端只能使用已登记的本机端口')
  }
  return url.toString()
}

function normalizeBackendBaseUrl(value: string): string {
  const url = parseRootUrl(value, 'Electron Backend 地址')
  if (url.protocol !== 'https:' && !isLoopbackHttpUrl(url)) {
    throw new Error('Electron Backend 只允许 HTTPS 或本机 HTTP')
  }
  return url.toString()
}

function parseRootUrl(value: string, label: string): URL {
  let url: URL
  try {
    url = new URL(value.trim())
  } catch {
    throw new Error(`${label}无效`)
  }
  if (
    url.pathname !== '/' ||
    url.search ||
    url.hash ||
    url.username ||
    url.password
  ) {
    throw new Error(`${label}必须是不含路径、凭据、查询或 Fragment 的 Origin`)
  }
  return url
}

function isLoopbackHttpUrl(url: URL): boolean {
  return (
    url.protocol === 'http:' &&
    (url.hostname === '127.0.0.1' || url.hostname === 'localhost')
  )
}
