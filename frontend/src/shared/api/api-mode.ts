export type ApiMode = 'mock' | 'real'

export function resolveApiMode(value: string | undefined): ApiMode {
  if (value === 'mock' || value === 'real') return value
  if (value === undefined || value.trim() === '') {
    throw new Error('VITE_API_MODE 必须显式设置为 mock 或 real')
  }
  throw new Error(`不支持的 VITE_API_MODE: ${value}`)
}
