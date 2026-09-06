import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig, loadEnv } from 'vite'

import { resolveApiMode } from './src/shared/api/api-mode'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const expectedApiMode =
    mode === 'production' || mode === 'real'
      ? 'real'
      : mode === 'mock'
        ? 'mock'
        : null
  if (expectedApiMode && resolveApiMode(env.VITE_API_MODE) !== expectedApiMode) {
    throw new Error(
      `${mode} 模式要求 VITE_API_MODE=${expectedApiMode}`,
    )
  }
  const proxy = env.VITE_API_PROXY_TARGET
    ? {
        '/api': {
          target: env.VITE_API_PROXY_TARGET,
          changeOrigin: true,
        },
      }
    : undefined

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: { proxy },
    preview: { proxy },
  }
})
