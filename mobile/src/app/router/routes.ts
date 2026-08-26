import type { RouteRecordRaw } from 'vue-router'

export const MOBILE_ROUTE_NAMES = {
  home: 'mobile-home',
  tasks: 'mobile-tasks',
  taskDetail: 'mobile-task-detail',
  devices: 'mobile-devices',
  deviceDetail: 'mobile-device-detail',
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

const taskRoutes: RouteRecordRaw[] = [
  {
    path: '/tasks',
    name: MOBILE_ROUTE_NAMES.tasks,
    component: () => import('@/pages/tasks/TaskCenterPage.vue'),
    meta: {
      title: '任务中心',
      requiresAuth: false,
      permission: null,
    },
  },
  {
    path: '/tasks/:taskId',
    name: MOBILE_ROUTE_NAMES.taskDetail,
    component: () => import('@/pages/tasks/TaskDetailPage.vue'),
    meta: {
      title: '任务详情',
      requiresAuth: false,
      permission: null,
    },
  },
]

const deviceRoutes: RouteRecordRaw[] = [
  {
    path: '/devices',
    name: MOBILE_ROUTE_NAMES.devices,
    component: () => import('@/pages/devices/DeviceCenterPage.vue'),
    meta: {
      title: '设备中心',
      requiresAuth: false,
      permission: null,
    },
  },
  {
    path: '/devices/:deviceId',
    name: MOBILE_ROUTE_NAMES.deviceDetail,
    component: () => import('@/pages/devices/DeviceDetailPage.vue'),
    meta: {
      title: '设备详情',
      requiresAuth: false,
      permission: null,
    },
  },
]

export function createMobileRoutes(
  options: CreateMobileRoutesOptions = {},
): RouteRecordRaw[] {
  const routes = [homeRoute, ...taskRoutes, ...deviceRoutes]
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
