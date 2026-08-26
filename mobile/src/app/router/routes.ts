import type { RouteRecordRaw } from 'vue-router'

export const MOBILE_ROUTE_NAMES = {
  home: 'mobile-home',
  foundation: 'mobile-foundation',
} as const

export interface CreateMobileRoutesOptions {
  includeFoundation?: boolean
  runtimeIsDevelopment?: boolean
}

const homeRoute: RouteRecordRaw = {
  path: '/',
  name: MOBILE_ROUTE_NAMES.home,
  component: () => import('@/pages/HomePage.vue'),
  meta: {
    title: '移动端',
    requiresAuth: false,
    permission: null,
  },
}

export function createMobileRoutes(
  options: CreateMobileRoutesOptions = {},
): RouteRecordRaw[] {
  const routes = [homeRoute]
  const runtimeIsDevelopment =
    options.runtimeIsDevelopment ?? import.meta.env.DEV
  const includeFoundation =
    import.meta.env.DEV &&
    runtimeIsDevelopment &&
    (options.includeFoundation ?? true)

  if (includeFoundation) {
    routes.push({
      path: '/__foundation',
      name: MOBILE_ROUTE_NAMES.foundation,
      component: () => import('@/pages/FoundationPage.vue'),
      meta: {
        title: '移动端基础设施',
        requiresAuth: false,
        permission: null,
      },
    })
  }

  return routes
}
