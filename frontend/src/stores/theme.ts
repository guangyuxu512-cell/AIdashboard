import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'

export type ThemeMode = 'light' | 'dark' | 'system'
export type ResolvedTheme = Exclude<ThemeMode, 'system'>

export const THEME_STORAGE_KEY = 'control-center.theme-mode'

function isThemeMode(value: string | null): value is ThemeMode {
  return value === 'light' || value === 'dark' || value === 'system'
}

function readStoredThemeMode(): ThemeMode {
  if (typeof window === 'undefined') return 'system'
  try {
    const value = window.localStorage.getItem(THEME_STORAGE_KEY)
    return isThemeMode(value) ? value : 'system'
  } catch {
    return 'system'
  }
}

function persistThemeMode(mode: ThemeMode): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, mode)
  } catch {
    // Theme persistence is optional when storage is unavailable.
  }
}

export const useThemeStore = defineStore('theme', () => {
  const mode = ref<ThemeMode>(readStoredThemeMode())
  const systemPrefersDark = ref(false)
  let initialized = false

  const resolvedTheme = computed<ResolvedTheme>(() =>
    mode.value === 'system'
      ? systemPrefersDark.value
        ? 'dark'
        : 'light'
      : mode.value,
  )

  function applyTheme(theme: ResolvedTheme): void {
    document.documentElement.dataset.theme = theme
    document.documentElement.style.colorScheme = theme
    window.desktop?.appearance.setTitleBarTheme(theme)
  }

  function setMode(value: ThemeMode): void {
    mode.value = value
  }

  function initialize(): void {
    if (initialized) return
    initialized = true

    const mediaQuery = window.matchMedia?.('(prefers-color-scheme: dark)')
    systemPrefersDark.value = mediaQuery?.matches ?? false
    mediaQuery?.addEventListener('change', (event) => {
      systemPrefersDark.value = event.matches
    })

    watch(mode, persistThemeMode, { flush: 'sync' })
    watch(resolvedTheme, applyTheme, { immediate: true, flush: 'sync' })
  }

  return { mode, resolvedTheme, initialize, setMode }
})
