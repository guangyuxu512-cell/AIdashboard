import 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    title: string
    requiresAuth: boolean
    permission: string | null
  }
}

export {}
