import { defineConfig } from '@playwright/test'

// No Backend, API seed or Electron. Shared size contracts only on registered 4176.
export default defineConfig({
  testDir: './e2e',
  testMatch: 'compact-list-foundation.spec.ts',
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:4176',
    viewport: { width: 1440, height: 900 },
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }
      : {},
  },
  webServer: {
    command:
      'pnpm exec vite --host 127.0.0.1 --port 4176 --strictPort --mode real',
    url: 'http://127.0.0.1:4176',
    reuseExistingServer: false,
    env: { VITE_API_MODE: 'real' },
  },
})
