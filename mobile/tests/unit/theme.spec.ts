import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { MOBILE_THEME_STORAGE_KEY, useThemeStore } from '@/app/stores/theme'

interface MatchMediaController {
  setMatches(matches: boolean): void
}

function installMatchMedia(initialMatches: boolean): MatchMediaController {
  let matches = initialMatches
  let listener: ((event: MediaQueryListEvent) => void) | undefined

  const mediaQuery = {
    get matches() {
      return matches
    },
    media: '(prefers-color-scheme: dark)',
    onchange: null,
    addEventListener: vi.fn(
      (_type: string, callback: (event: MediaQueryListEvent) => void) => {
        listener = callback
      },
    ),
    removeEventListener: vi.fn(),
    addListener: vi.fn((callback: (event: MediaQueryListEvent) => void) => {
      listener = callback
    }),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(() => true),
  } as unknown as MediaQueryList

  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn(() => mediaQuery),
  })

  return {
    setMatches(nextMatches: boolean) {
      matches = nextMatches
      listener?.({ matches: nextMatches } as MediaQueryListEvent)
    },
  }
}

describe('useThemeStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    window.localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
    document.documentElement.classList.remove('van-theme-dark')
    document.documentElement.style.removeProperty('color-scheme')
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('resolves system mode and applies the Vant dark class', () => {
    installMatchMedia(true)
    const store = useThemeStore()

    store.initialize()

    expect(store.mode).toBe('system')
    expect(store.resolvedTheme).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(document.documentElement.classList.contains('van-theme-dark')).toBe(
      true,
    )
    store.$dispose()
  })

  it('persists an explicit mode and updates the root theme', () => {
    installMatchMedia(false)
    const store = useThemeStore()
    store.initialize()

    store.setMode('dark')

    expect(window.localStorage.getItem(MOBILE_THEME_STORAGE_KEY)).toBe('dark')
    expect(store.resolvedTheme).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
    store.$dispose()
  })

  it('reacts to system color scheme changes while in system mode', () => {
    const matchMedia = installMatchMedia(false)
    const store = useThemeStore()
    store.initialize()

    matchMedia.setMatches(true)

    expect(store.resolvedTheme).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
    store.$dispose()
  })

  it('ignores an invalid stored theme mode', () => {
    window.localStorage.setItem(MOBILE_THEME_STORAGE_KEY, 'unknown')
    installMatchMedia(false)

    const store = useThemeStore()
    store.initialize()

    expect(store.mode).toBe('system')
    expect(store.resolvedTheme).toBe('light')
    store.$dispose()
  })
})
