import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { THEME_STORAGE_KEY, useThemeStore } from './theme'

function mockSystemTheme(initialMatches: boolean) {
  let listener: ((event: MediaQueryListEvent) => void) | undefined
  const mediaQuery = {
    matches: initialMatches,
    media: '(prefers-color-scheme: dark)',
    onchange: null,
    addEventListener: vi.fn(
      (_event: string, callback: (event: MediaQueryListEvent) => void) => {
        listener = callback
      },
    ),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  } as unknown as MediaQueryList

  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => mediaQuery),
  )

  return {
    change(matches: boolean) {
      listener?.({ matches } as MediaQueryListEvent)
    },
  }
}

describe('theme store', () => {
  beforeEach(() => {
    window.localStorage.clear()
    delete window.desktop
    delete document.documentElement.dataset.theme
    document.documentElement.style.colorScheme = ''
    setActivePinia(createPinia())
  })

  it('persists an explicit theme and applies it to the document root', () => {
    mockSystemTheme(false)
    const store = useThemeStore()
    store.initialize()
    store.setMode('dark')

    expect(store.resolvedTheme).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
  })

  it('tracks live system color scheme changes in system mode', () => {
    const systemTheme = mockSystemTheme(false)
    const store = useThemeStore()
    store.initialize()

    expect(store.mode).toBe('system')
    expect(store.resolvedTheme).toBe('light')

    systemTheme.change(true)
    expect(store.resolvedTheme).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('restores a valid persisted theme', () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, 'dark')
    mockSystemTheme(false)
    const store = useThemeStore()
    store.initialize()

    expect(store.mode).toBe('dark')
    expect(store.resolvedTheme).toBe('dark')
  })

  it('syncs the resolved theme to the Electron title bar when available', () => {
    const setTitleBarTheme = vi.fn()
    window.desktop = { appearance: { setTitleBarTheme } }
    mockSystemTheme(false)

    const store = useThemeStore()
    store.initialize()
    store.setMode('dark')

    expect(setTitleBarTheme).toHaveBeenNthCalledWith(1, 'light')
    expect(setTitleBarTheme).toHaveBeenLastCalledWith('dark')
  })
})
