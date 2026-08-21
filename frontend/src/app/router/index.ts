import { createRouter, createWebHashHistory } from 'vue-router'

import { requireModuleDefinition } from '@/app/modules/registry'

const foundationModule = requireModuleDefinition('foundation')
const shopModule = requireModuleDefinition('shop')
const deviceModule = requireModuleDefinition('device')

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: foundationModule.routePath,
      name: foundationModule.routeName,
      component: () => import('@/pages/HomePage.vue'),
      meta: { moduleCode: foundationModule.moduleCode },
    },
    {
      path: shopModule.routePath,
      name: shopModule.routeName,
      component: () => import('@/pages/shops/ShopCenterPage.vue'),
      meta: { moduleCode: shopModule.moduleCode },
    },
    {
      path: deviceModule.routePath,
      name: deviceModule.routeName,
      component: () => import('@/pages/devices/DeviceCenterPage.vue'),
      meta: { moduleCode: deviceModule.moduleCode },
    },
  ],
})

export default router
