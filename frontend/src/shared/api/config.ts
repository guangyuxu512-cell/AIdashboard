export type ApiMode = 'mock' | 'real'

function resolveApiMode(value: string | undefined): ApiMode {
  if (value === undefined || value === 'mock') return 'mock'
  if (value === 'real') return 'real'
  throw new Error(`不支持的 VITE_API_MODE: ${value}`)
}

export const apiMode = resolveApiMode(import.meta.env.VITE_API_MODE)
export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim() || '/'
export const apiTimeoutMs = 10_000
