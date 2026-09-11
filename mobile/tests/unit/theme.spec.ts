import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { MOBILE_THEME_STORAGE_KEY, useThemeStore } from '@/app/stores/theme'

interface MatchMediaController {
  setMatches(matches: boolean): void
  setMatchesWithoutEvent(matches: boolean): void
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
    setMatchesWithoutEvent(nextMatches: boolean) {
      matches = nextMatches
    },
  }
}

function installThemeMetadata(): void {
  const themeColorMeta = document.createElement('meta')
  themeColorMeta.name = 'theme-color'
  themeColorMeta.dataset.mobileThemeColor = ''
  themeColorMeta.content = '#fbfcfe'
  document.head.append(themeColorMeta)

  const appleStatusBarMeta = document.createElement('meta')
  appleStatusBarMeta.name = 'apple-mobile-web-app-status-bar-style'
  appleStatusBarMeta.content = 'default'
  document.head.append(appleStatusBarMeta)

  const themeTokens = document.createElement('style')
  themeTokens.dataset.testThemeTokens = ''
  themeTokens.textContent = `
    :root[data-theme='light'] { --mobile-browser-theme-color: #fbfcfe; }
    :root[data-theme='dark'] { --mobile-browser-theme-color: #07111d; }
  `
  document.head.append(themeTokens)
}

describe('useThemeStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    window.localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
    document.documentElement.classList.remove('van-theme-dark')
    document.documentElement.style.removeProperty('color-scheme')
    document
      .querySelectorAll('[data-mobile-theme-color], [data-test-theme-tokens]')
      .forEach((element) => element.remove())
    document
      .querySelectorAll('meta[name="apple-mobile-web-app-status-bar-style"]')
      .forEach((element) => element.remove())
    installThemeMetadata()
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
    expect(
      document.querySelector<HTMLMetaElement>(
        'meta[name="theme-color"][data-mobile-theme-color]',
      )?.content,
    ).toBe('#07111d')
    expect(
      document.querySelector<HTMLMetaElement>(
        'meta[name="apple-mobile-web-app-status-bar-style"]',
      )?.content,
    ).toBe('black-translucent')
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

  it('synchronizes browser chrome after background resume and orientation changes', () => {
    const matchMedia = installMatchMedia(false)
    const store = useThemeStore()
    store.initialize()

    expect(
      document.querySelector<HTMLMetaElement>(
        'meta[name="theme-color"][data-mobile-theme-color]',
      )?.content,
    ).toBe('#fbfcfe')

    matchMedia.setMatchesWithoutEvent(true)
    document.dispatchEvent(new Event('visibilitychange'))

    expect(store.resolvedTheme).toBe('dark')
    expect(
      document.querySelector<HTMLMetaElement>(
        'meta[name="theme-color"][data-mobile-theme-color]',
      )?.content,
    ).toBe('#07111d')
    expect(
      document.querySelector<HTMLMetaElement>(
        'meta[name="apple-mobile-web-app-status-bar-style"]',
      )?.content,
    ).toBe('black-translucent')

    matchMedia.setMatchesWithoutEvent(false)
    window.dispatchEvent(new Event('orientationchange'))

    expect(store.resolvedTheme).toBe('light')
    expect(
      document.querySelector<HTMLMetaElement>(
        'meta[name="theme-color"][data-mobile-theme-color]',
      )?.content,
    ).toBe('#fbfcfe')
    expect(
      document.querySelector<HTMLMetaElement>(
        'meta[name="apple-mobile-web-app-status-bar-style"]',
      )?.content,
    ).toBe('default')
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

  it.each([
    [false, 'dark'],
    [true, 'light'],
  ] as const)(
    'quick toggles system resolved dark=%s to the opposite explicit mode',
    (systemPrefersDark, expectedMode) => {
      installMatchMedia(systemPrefersDark)
      const store = useThemeStore()
      store.initialize()

      expect(store.mode).toBe('system')
      store.toggleResolvedTheme()

      expect(store.mode).toBe(expectedMode)
      expect(store.resolvedTheme).toBe(expectedMode)
      store.$dispose()
    },
  )

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
