declare global {
  interface Window {
    desktop?: {
      appearance: {
        setTitleBarTheme(theme: 'light' | 'dark'): void
      }
    }
  }
}

export {}
