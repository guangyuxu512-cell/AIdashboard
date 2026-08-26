import 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    title: string
    layout: 'main' | 'detail'
    requiresAuth: boolean
    permission: string | null
  }
}

export {}
