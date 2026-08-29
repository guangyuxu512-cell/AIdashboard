import 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    title: string
    layout: 'main' | 'detail' | 'tool'
    requiresAuth: boolean
    permission: string | null
  }
}

export {}
