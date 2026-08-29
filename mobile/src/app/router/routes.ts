import type { RouteRecordRaw } from 'vue-router'

export const MOBILE_ROUTE_NAMES = {
  home: 'mobile-home',
  tasks: 'mobile-tasks',
  taskDetail: 'mobile-task-detail',
  devices: 'mobile-devices',
  deviceDetail: 'mobile-device-detail',
  schedules: 'mobile-schedules',
  shops: 'mobile-shops',
  profile: 'mobile-profile',
  foundation: 'mobile-foundation',
  visualTokenTuner: 'mobile-visual-token-tuner',
} as const

export interface CreateMobileRoutesOptions {
  includeFoundation?: boolean
  includeVisualTokenTuner?: boolean
  runtimeIsDevelopment?: boolean
}

const homeRoute: RouteRecordRaw = {
  path: '/',
  name: MOBILE_ROUTE_NAMES.home,
  component: () => import('@/pages/HomePage.vue'),
  meta: {
    title: '移动端',
    layout: 'main',
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
      layout: 'main',
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
      layout: 'detail',
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
      layout: 'main',
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
      layout: 'detail',
      requiresAuth: false,
      permission: null,
    },
  },
]

const comingSoonPage = () => import('@/pages/ComingSoonPage.vue')

const placeholderRoutes: RouteRecordRaw[] = [
  {
    path: '/schedules',
    name: MOBILE_ROUTE_NAMES.schedules,
    component: comingSoonPage,
    meta: {
      title: '定时计划',
      layout: 'main',
      requiresAuth: false,
      permission: null,
    },
  },
  {
    path: '/shops',
    name: MOBILE_ROUTE_NAMES.shops,
    component: comingSoonPage,
    meta: {
      title: '店铺',
      layout: 'main',
      requiresAuth: false,
      permission: null,
    },
  },
  {
    path: '/me',
    name: MOBILE_ROUTE_NAMES.profile,
    component: comingSoonPage,
    meta: {
      title: '我的',
      layout: 'main',
      requiresAuth: false,
      permission: null,
    },
  },
]

export function createMobileRoutes(
  options: CreateMobileRoutesOptions = {},
): RouteRecordRaw[] {
  const routes = [
    homeRoute,
    ...taskRoutes,
    ...deviceRoutes,
    ...placeholderRoutes,
  ]
  const runtimeIsDevelopment =
    options.runtimeIsDevelopment ?? import.meta.env.DEV
  const includeFoundation =
    import.meta.env.DEV &&
    runtimeIsDevelopment &&
    (options.includeFoundation ?? true)
  const includeVisualTokenTuner =
    import.meta.env.DEV &&
    runtimeIsDevelopment &&
    import.meta.env.VITE_VISUAL_TUNER !== 'false' &&
    (options.includeVisualTokenTuner ?? true)

  if (includeFoundation) {
    routes.push({
      path: '/__foundation',
      name: MOBILE_ROUTE_NAMES.foundation,
      component: () => import('@/pages/FoundationPage.vue'),
      meta: {
        title: '移动端基础设施',
        layout: 'detail',
        requiresAuth: false,
        permission: null,
      },
    })
  }

  if (includeVisualTokenTuner) {
    routes.push({
      path: '/__visual-tuner',
      name: MOBILE_ROUTE_NAMES.visualTokenTuner,
      component: () =>
        import('@/dev/visual-token-tuner/VisualTokenTunerPage.vue'),
      meta: {
        title: '视觉 Token 调参器',
        layout: 'tool',
        requiresAuth: false,
        permission: null,
      },
    })
  }

  return routes
}
