import { createRouter, createWebHashHistory } from 'vue-router'

import { requireModuleDefinition } from '@/app/modules/registry'

const foundationModule = requireModuleDefinition('foundation')
const shopModule = requireModuleDefinition('shop')
const deviceModule = requireModuleDefinition('device')
const taskModule = requireModuleDefinition('task')
const scheduleModule = requireModuleDefinition('schedule')
const settingsModule = requireModuleDefinition('settings')

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
    {
      path: taskModule.routePath,
      name: taskModule.routeName,
      component: () => import('@/pages/tasks/TaskCenterPage.vue'),
      meta: { moduleCode: taskModule.moduleCode },
    },
    {
      path: scheduleModule.routePath,
      name: scheduleModule.routeName,
      component: () => import('@/pages/schedules/ScheduleCenterPage.vue'),
      meta: { moduleCode: scheduleModule.moduleCode },
    },
    {
      path: settingsModule.routePath,
      name: settingsModule.routeName,
      component: () => import('@/pages/settings/NotificationSettingsPage.vue'),
      meta: { moduleCode: settingsModule.moduleCode },
    },
  ],
})

export default router
