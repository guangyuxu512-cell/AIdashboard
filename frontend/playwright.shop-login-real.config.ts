import { defineConfig } from '@playwright/test'

// Owner's registered frontend port. All API and desktop actions are intercepted;
// this is a browser contract check, not native Electron/platform evidence.
const port = process.env.PLAYWRIGHT_FRONTEND_PORT ?? '4176'
export default defineConfig({
  testDir: './e2e/production',
  testMatch: 'shop-login-sync.spec.ts',
  use: { baseURL: `http://127.0.0.1:${port}` },
  webServer: {
    command: `pnpm exec vite --host 127.0.0.1 --port ${port} --strictPort --mode real`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: false,
    env: { VITE_API_MODE: 'real' },
  },
})
