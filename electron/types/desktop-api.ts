export type DesktopResolvedTheme = 'light' | 'dark'

export const desktopIpcChannels = {
  setTitleBarTheme: 'appearance:set-title-bar-theme',
} as const

export interface DesktopApi {
  appearance: {
    setTitleBarTheme(theme: DesktopResolvedTheme): void
  }
}

export function isDesktopResolvedTheme(
  value: unknown,
): value is DesktopResolvedTheme {
  return value === 'light' || value === 'dark'
}
