/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_MODE?: 'mock' | 'real'
  readonly VITE_API_BASE_URL?: string
  readonly VITE_API_PROXY_TARGET?: string
  readonly VITE_SHOW_DEVELOPMENT_MODULES?: 'true' | 'false'
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
