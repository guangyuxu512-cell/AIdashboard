import { createRouter, createWebHashHistory, type Router } from 'vue-router'

import { createMobileRoutes, type CreateMobileRoutesOptions } from './routes'

export function createMobileRouter(
  options: CreateMobileRoutesOptions = {},
): Router {
  return createRouter({
    history: createWebHashHistory(),
    routes: createMobileRoutes(options),
  })
}

const router = createMobileRouter()

export default router
