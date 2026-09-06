import { resolveApiMode } from './api-mode'

export type { ApiMode } from './api-mode'

export const apiMode = resolveApiMode(import.meta.env.VITE_API_MODE)
export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim() || '/'
export const apiTimeoutMs = 10_000
