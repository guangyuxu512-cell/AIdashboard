import { defineConfig } from '@playwright/test'

const apiMode = process.env.PLAYWRIGHT_API_MODE === 'real' ? 'real' : 'mock'

export default defineConfig({
  testDir: './e2e',
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
            command:
              '".venv\\Scripts\\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000',
            cwd: '../backend',
            url: 'http://127.0.0.1:8000/health',
            reuseExistingServer: false,
          },
        ]
      : []),
  ],
})
