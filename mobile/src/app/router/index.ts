import { createRouter, createWebHashHistory, type Router } from 'vue-router'

import { createMobileRoutes, type CreateMobileRoutesOptions } from './routes'

export function createMobileRouter(
  options: CreateMobileRoutesOptions = {},
): Router {
  return createRouter({
    history: createWebHashHistory(import.meta.env.BASE_URL),
    routes: createMobileRoutes(options),
  })
}

const router = createMobileRouter()

export default router
