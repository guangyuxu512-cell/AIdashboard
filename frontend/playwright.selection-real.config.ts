import { defineConfig } from '@playwright/test'

// Frontend-only real-mode check; intercepted auth, no Backend process or DB seed.
const port = process.env.PLAYWRIGHT_FRONTEND_PORT ?? '4176'
export default defineConfig({
  testDir: './e2e/production',
  testMatch: [
    'product-selection-candidate-results.spec.ts',
    'product-selection-unavailable.spec.ts',
    'product-selection-strategy-restoration.spec.ts',
    'product-selection-strategies.spec.ts',
    'product-selection-strategy-position.spec.ts',
  ],
  use: { baseURL: `http://127.0.0.1:${port}` },
  webServer: {
    command: `pnpm exec vite --host 127.0.0.1 --port ${port} --strictPort --mode real`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: false,
    env: { VITE_API_MODE: 'real' },
  },
})
