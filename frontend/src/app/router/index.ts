import { createRouter, createWebHashHistory } from 'vue-router'

import { requireModuleDefinition } from '@/app/modules/registry'

const foundationModule = requireModuleDefinition('foundation')
const assetModule = requireModuleDefinition('asset')
const operatingDashboardModule = requireModuleDefinition('operating-dashboard')
const deviceModule = requireModuleDefinition('device')
const workerShopsModule = requireModuleDefinition('worker-shops')
const taskModule = requireModuleDefinition('task')
const scheduleModule = requireModuleDefinition('schedule')
const settingsModule = requireModuleDefinition('settings')

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      redirect: deviceModule.routePath,
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/pages/auth/LoginPage.vue'),
      meta: { public: true, layout: 'auth' },
    },
    {
      path: foundationModule.routePath,
      name: foundationModule.routeName,
      component: () => import('@/pages/HomePage.vue'),
      meta: { moduleCode: foundationModule.moduleCode },
    },
    {
      path: assetModule.routePath,
      name: assetModule.routeName,
      component: () => import('@/pages/assets/AssetLibraryPage.vue'),
      meta: { moduleCode: assetModule.moduleCode },
    },
    {
      path: operatingDashboardModule.routePath,
      name: operatingDashboardModule.routeName,
      component: () =>
        import('@/pages/operating-dashboard/OperatingDashboardPage.vue'),
      meta: { moduleCode: operatingDashboardModule.moduleCode },
    },
    {
      path: deviceModule.routePath,
      name: deviceModule.routeName,
      component: () => import('@/pages/devices/DeviceCenterPage.vue'),
      meta: { moduleCode: deviceModule.moduleCode },
    },
    {
      path: workerShopsModule.routePath,
      name: workerShopsModule.routeName,
      component: () => import('@/pages/devices/WorkerShopsPage.vue'),
      meta: { moduleCode: workerShopsModule.moduleCode },
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
    {
      path: '/settings/users',
      name: 'access-management',
      component: () => import('@/pages/settings/AccessManagementPage.vue'),
      meta: { requiresAccessAdministrator: true },
    },
    {
      path: '/settings/audit-logs',
      name: 'audit-logs',
      component: () => import('@/pages/settings/AuditLogPage.vue'),
      meta: { requiresAccessAdministrator: true },
    },
    {
      path: '/permission-denied',
      name: 'permission-denied',
      component: () => import('@/pages/PermissionDeniedPage.vue'),
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: deviceModule.routePath,
    },
  ],
})

export default router
