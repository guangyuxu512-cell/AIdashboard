import { computed, onScopeDispose, ref, watch } from 'vue'
import { defineStore } from 'pinia'

export type ThemeMode = 'light' | 'dark' | 'system'
export type ResolvedTheme = Exclude<ThemeMode, 'system'>

export const MOBILE_THEME_STORAGE_KEY = 'control-center.mobile.theme-mode'

const DARK_SCHEME_QUERY = '(prefers-color-scheme: dark)'

function isThemeMode(value: string | null): value is ThemeMode {
  return value === 'light' || value === 'dark' || value === 'system'
}

function readStoredThemeMode(): ThemeMode {
  if (typeof window === 'undefined') return 'system'

  try {
    const storedMode = window.localStorage.getItem(MOBILE_THEME_STORAGE_KEY)
    return isThemeMode(storedMode) ? storedMode : 'system'
  } catch {
    return 'system'
  }
}

function persistThemeMode(mode: ThemeMode): void {
  if (typeof window === 'undefined') return

  try {
    window.localStorage.setItem(MOBILE_THEME_STORAGE_KEY, mode)
  } catch {
    // Theme persistence is optional when browser storage is unavailable.
  }
}

function applyResolvedTheme(theme: ResolvedTheme): void {
  if (typeof document === 'undefined') return

  const root = document.documentElement
  root.dataset.theme = theme
  root.style.colorScheme = theme
  root.classList.toggle('van-theme-dark', theme === 'dark')
}

export const useThemeStore = defineStore('mobile-theme', () => {
  const mode = ref<ThemeMode>(readStoredThemeMode())
  const systemPrefersDark = ref(false)
  let initialized = false
  let mediaQuery: MediaQueryList | null = null

  const resolvedTheme = computed<ResolvedTheme>(() =>
    mode.value === 'system'
      ? systemPrefersDark.value
        ? 'dark'
        : 'light'
      : mode.value,
  )

  const handleSystemThemeChange = (event: Pick<MediaQueryList, 'matches'>) => {
    systemPrefersDark.value = event.matches
  }

  const addSystemThemeListener = (query: MediaQueryList): void => {
    if (typeof query.addEventListener === 'function') {
      query.addEventListener('change', handleSystemThemeChange)
      return
    }
    query.addListener(handleSystemThemeChange)
  }

  const removeSystemThemeListener = (query: MediaQueryList): void => {
    if (typeof query.removeEventListener === 'function') {
      query.removeEventListener('change', handleSystemThemeChange)
      return
    }
    query.removeListener(handleSystemThemeChange)
  }

  function setMode(nextMode: ThemeMode): void {
    mode.value = nextMode
  }

  function toggleResolvedTheme(): void {
    setMode(resolvedTheme.value === 'dark' ? 'light' : 'dark')
  }

  function initialize(): void {
    if (initialized) return
    initialized = true

    if (typeof window !== 'undefined' && window.matchMedia) {
      mediaQuery = window.matchMedia(DARK_SCHEME_QUERY)
      systemPrefersDark.value = mediaQuery.matches
      addSystemThemeListener(mediaQuery)
    }

    watch(mode, persistThemeMode, { flush: 'sync' })
    watch(resolvedTheme, applyResolvedTheme, {
      immediate: true,
      flush: 'sync',
    })
  }

  onScopeDispose(() => {
    if (mediaQuery) removeSystemThemeListener(mediaQuery)
  })

  return { mode, resolvedTheme, setMode, toggleResolvedTheme, initialize }
})
