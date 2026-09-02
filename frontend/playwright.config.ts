import { defineConfig } from '@playwright/test'

const apiMode = process.env.PLAYWRIGHT_API_MODE === 'real' ? 'real' : 'mock'
const backendPort = process.env.PLAYWRIGHT_BACKEND_PORT ?? '8000'

export default defineConfig({
  testDir: './e2e',
  testIgnore: '**/production/**',
  use: {
    baseURL: 'http://127.0.0.1:4173',
  },
  webServer: [
    {
      command: `pnpm exec vite --host 127.0.0.1 --port 4173 --mode ${apiMode}`,
      url: 'http://127.0.0.1:4173',
      reuseExistingServer: false,
    },
    ...(apiMode === 'real'
      ? [
          {
            command: `".venv\\Scripts\\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port ${backendPort}`,
            cwd: '../backend',
            url: `http://127.0.0.1:${backendPort}/health`,
            reuseExistingServer: false,
          },
        ]
      : []),
  ],
})
