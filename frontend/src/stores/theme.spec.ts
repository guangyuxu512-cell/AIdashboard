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
    delete document.documentElement.dataset.themePreset
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
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('midnight')
  })

  it('tracks live system color scheme changes in system mode', () => {
    const systemTheme = mockSystemTheme(false)
    const store = useThemeStore()
    store.initialize()

    store.setMode('system')
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

    expect(store.mode).toBe('midnight')
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

  it('defaults to graphite even when the system is dark', () => {
    mockSystemTheme(true)
    const store = useThemeStore()
    store.initialize()
    expect(store.mode).toBe('graphite')
    expect(store.resolvedPreset).toBe('graphite')
    expect(store.resolvedTheme).toBe('light')
  })

  it.each(['graphite', 'forest', 'coral', 'midnight'] as const)(
    'applies and restores %s without changing the persistence key',
    (preset) => {
      mockSystemTheme(false)
      const store = useThemeStore()
      store.initialize()
      store.setMode(preset)
      expect(store.resolvedPreset).toBe(preset)
      expect(document.documentElement.dataset.themePreset).toBe(preset)
      expect(document.documentElement.style.colorScheme).toBe(
        preset === 'midnight' ? 'dark' : 'light',
      )
      // The initial default is not written until a preference is chosen.
      if (preset === 'graphite') store.setMode('forest')
      store.setMode(preset)
      expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe(preset)
      setActivePinia(createPinia())
      const reopened = useThemeStore()
      reopened.initialize()
      expect(reopened.mode).toBe(preset)
    },
  )

  it('maps old light preferences and ignores malformed preferences', () => {
    mockSystemTheme(true)
    for (const preference of ['light', 'invalid']) {
      window.localStorage.setItem(THEME_STORAGE_KEY, preference)
      setActivePinia(createPinia())
      const store = useThemeStore()
      store.initialize()
      expect(store.mode).toBe('graphite')
    }
  })

  it('updates the preset for light-to-light changes without redundant native mode calls', () => {
    const setTitleBarTheme = vi.fn()
    window.desktop = { appearance: { setTitleBarTheme } }
    mockSystemTheme(false)
    const store = useThemeStore()
    store.initialize()
    store.setMode('forest')
    expect(document.documentElement.dataset.themePreset).toBe('forest')
    store.setMode('coral')
    expect(document.documentElement.dataset.themePreset).toBe('coral')
    expect(store.resolvedTheme).toBe('light')
    expect(setTitleBarTheme).toHaveBeenCalledTimes(1)
  })
})
