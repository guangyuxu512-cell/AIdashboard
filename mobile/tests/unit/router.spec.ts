import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia } from 'pinia'
import type { NavigationGuard, Router } from 'vue-router'
import { createMemoryHistory, createRouter } from 'vue-router'

import { createMobileRouter } from '@/app/router'
import {
  createMobileAuthGuard,
  createMobilePermissionGuard,
  installRouteAccessGuards,
} from '@/app/router/access'
import { createMobileRoutes, MOBILE_ROUTE_NAMES } from '@/app/router/routes'
import { configureAuthEffects, useAuthStore } from '@/app/stores/auth'
import type {
  HumanAuthDataSource,
  HumanTeamMembership,
} from '@/entities/human-auth'
import { ApiClientError } from '@/shared/api'

function membership(teamId = 'team-1'): HumanTeamMembership {
  return {
    membershipId: `membership-${teamId}`,
    teamId,
    teamName: teamId === 'team-1' ? '默认团队' : '运营团队',
    teamEnabled: true,
    roleCode: 'member',
    dataScope: 'team',
    membershipEnabled: true,
  }
}

function authDataSource(options: {
  authenticated?: boolean
  moduleCodes?: string[]
  teams?: HumanTeamMembership[]
}): HumanAuthDataSource {
  const currentUser = { userId: 'user-1', displayName: '测试人员' }
  return {
    login: vi.fn().mockResolvedValue(currentUser),
    logout: vi.fn().mockResolvedValue(undefined),
    getCurrentUser:
      options.authenticated === false
        ? vi.fn().mockRejectedValue(
            new ApiClientError({
              code: 'HUMAN_AUTHENTICATION_REQUIRED',
              message: '需要有效的管理端用户身份',
              status: 401,
            }),
          )
        : vi.fn().mockResolvedValue(currentUser),
    listMyTeams: vi.fn().mockResolvedValue(options.teams ?? [membership()]),
    getCurrentModuleAccess: vi.fn().mockResolvedValue({
      moduleCodes: options.moduleCodes ?? ['device', 'task'],
      isAccessAdministrator: false,
    }),
  }
}

function createGuardedRouter(options: {
  authenticated?: boolean
  moduleCodes?: string[]
  teams?: HumanTeamMembership[]
}) {
  const pinia = createPinia()
  const auth = useAuthStore(pinia)
  auth.setDataSource(authDataSource(options))
  const router = createRouter({
    history: createMemoryHistory(),
    routes: createMobileRoutes({ runtimeIsDevelopment: false }),
  })
  installRouteAccessGuards(router, {
    authGuard: createMobileAuthGuard(pinia),
    permissionGuard: createMobilePermissionGuard(pinia),
  })
  return { auth, router }
}

describe('mobile router', () => {
  beforeEach(() => {
    window.localStorage.clear()
    configureAuthEffects({
      onTeamChanged: () => undefined,
      onAuthCleared: () => undefined,
    })
  })

  it('declares explicit access metadata for every route', () => {
    const routes = createMobileRoutes({ includeFoundation: true })

    for (const route of routes) {
      expect(route.meta).toEqual(
        expect.objectContaining({
          title: expect.any(String),
          layout: expect.stringMatching(/^(main|detail|auth|tool)$/),
          requiresAuth: expect.any(Boolean),
        }),
      )
      expect(
        route.meta?.permission === null ||
          typeof route.meta?.permission === 'string',
      ).toBe(true)
    }
  })

  it('keeps development-only routes out of a production route table', () => {
    const productionRoutes = createMobileRoutes({
      runtimeIsDevelopment: false,
    })

    expect(
      productionRoutes.some(
        (route) => route.name === MOBILE_ROUTE_NAMES.foundation,
      ),
    ).toBe(false)
    expect(productionRoutes.map((route) => route.path)).toEqual([
      '/login',
      '/',
      '/tasks',
      '/tasks/:taskId',
      '/devices',
      '/devices/:deviceId',
      '/schedules',
      '/shops',
      '/me',
      '/permission-denied',
    ])
  })

  it('protects formal product routes with their Backend module codes', () => {
    const routes = createMobileRoutes({ runtimeIsDevelopment: false })
    const expectedAccess = new Map([
      [MOBILE_ROUTE_NAMES.tasks, ['main', 'task']],
      [MOBILE_ROUTE_NAMES.taskDetail, ['detail', 'task']],
      [MOBILE_ROUTE_NAMES.devices, ['main', 'device']],
      [MOBILE_ROUTE_NAMES.deviceDetail, ['detail', 'device']],
      [MOBILE_ROUTE_NAMES.schedules, ['main', 'schedule']],
      [MOBILE_ROUTE_NAMES.shops, ['main', 'shop']],
      [MOBILE_ROUTE_NAMES.profile, ['main', null]],
    ])

    for (const [routeName, [layout, permission]] of expectedAccess) {
      const route = routes.find((candidate) => candidate.name === routeName)
      expect(route?.meta).toEqual(
        expect.objectContaining({
          layout,
          requiresAuth: true,
          permission,
        }),
      )
    }
  })

  it('registers a public auth layout and a protected denied page', () => {
    const routes = createMobileRoutes({ runtimeIsDevelopment: false })

    expect(
      routes.find((route) => route.name === MOBILE_ROUTE_NAMES.login),
    ).toEqual(
      expect.objectContaining({
        path: '/login',
        meta: expect.objectContaining({
          layout: 'auth',
          requiresAuth: false,
          permission: null,
        }),
      }),
    )
    expect(
      routes.find((route) => route.name === MOBILE_ROUTE_NAMES.permissionDenied)
        ?.meta,
    ).toEqual(expect.objectContaining({ requiresAuth: true, permission: null }))
  })

  it('keeps only schedule and shop on the shared coming-soon page', () => {
    const routes = createMobileRoutes({ runtimeIsDevelopment: false })
    const schedule = routes.find(
      (route) => route.name === MOBILE_ROUTE_NAMES.schedules,
    )
    const shop = routes.find((route) => route.name === MOBILE_ROUTE_NAMES.shops)
    const profile = routes.find(
      (route) => route.name === MOBILE_ROUTE_NAMES.profile,
    )

    expect(schedule?.component).toBe(shop?.component)
    expect(profile?.component).not.toBe(schedule?.component)
  })

  it('registers development tools as public tool routes only in development', () => {
    const developmentRoutes = createMobileRoutes({
      includeFoundation: true,
      includeVisualTokenTuner: true,
      includeIconGallery: true,
    })
    const productionRoutes = createMobileRoutes({
      runtimeIsDevelopment: false,
      includeFoundation: true,
      includeVisualTokenTuner: true,
      includeIconGallery: true,
    })

    for (const name of [
      MOBILE_ROUTE_NAMES.foundation,
      MOBILE_ROUTE_NAMES.visualTokenTuner,
      MOBILE_ROUTE_NAMES.iconGallery,
    ]) {
      expect(
        developmentRoutes.find((route) => route.name === name)?.meta,
      ).toEqual(
        expect.objectContaining({ requiresAuth: false, permission: null }),
      )
      expect(productionRoutes.some((route) => route.name === name)).toBe(false)
    }
  })

  it('uses hash history', () => {
    const router = createMobileRouter({ includeFoundation: false })

    expect(router.options.history.createHref('/')).toContain('#/')
  })

  it('redirects an anonymous deep link to login with a safe return path', async () => {
    const { router } = createGuardedRouter({ authenticated: false })

    await router.push('/tasks')

    expect(router.currentRoute.value).toEqual(
      expect.objectContaining({
        name: MOBILE_ROUTE_NAMES.login,
        query: { redirect: '/tasks' },
      }),
    )
  })

  it('restores a valid session and permits modules granted to the active membership', async () => {
    const { auth, router } = createGuardedRouter({
      moduleCodes: ['device', 'task'],
    })

    await router.push('/devices')

    expect(router.currentRoute.value.name).toBe(MOBILE_ROUTE_NAMES.devices)
    expect(auth.isAuthenticated).toBe(true)
    expect(auth.activeTeamId).toBe('team-1')
  })

  it.each([
    ['/devices', MOBILE_ROUTE_NAMES.devices],
    ['/tasks', MOBILE_ROUTE_NAMES.tasks],
  ] as const)(
    'rejects direct navigation to %s without its module grant',
    async (path, deniedRouteName) => {
      const allowedCode =
        deniedRouteName === MOBILE_ROUTE_NAMES.devices ? 'task' : 'device'
      const { router } = createGuardedRouter({
        moduleCodes: [allowedCode],
      })

      await router.push(path)

      expect(router.currentRoute.value.name).toBe(
        MOBILE_ROUTE_NAMES.permissionDenied,
      )
    },
  )

  it('returns a multi-team user to login until a real team is selected', async () => {
    const { auth, router } = createGuardedRouter({
      teams: [membership('team-1'), membership('team-2')],
    })

    await router.push('/tasks')

    expect(router.currentRoute.value.name).toBe(MOBILE_ROUTE_NAMES.login)
    expect(auth.isAuthenticated).toBe(true)
    expect(auth.requiresTeamSelection).toBe(true)
  })

  it('redirects an already authenticated login visit to the first permitted module', async () => {
    const { router } = createGuardedRouter({ moduleCodes: ['task'] })

    await router.push('/login')

    expect(router.currentRoute.value.name).toBe(MOBILE_ROUTE_NAMES.tasks)
  })

  it('installs named Auth and Permission guards in a fixed order', () => {
    const removeAuthGuard = vi.fn()
    const removePermissionGuard = vi.fn()
    const beforeEach = vi
      .fn()
      .mockReturnValueOnce(removeAuthGuard)
      .mockReturnValueOnce(removePermissionGuard)
    const router = { beforeEach } as unknown as Router
    const authGuard = vi.fn(() => true) as NavigationGuard
    const permissionGuard = vi.fn(() => true) as NavigationGuard

    const remove = installRouteAccessGuards(router, {
      authGuard,
      permissionGuard,
    })

    expect(beforeEach.mock.calls).toEqual([[authGuard], [permissionGuard]])

    remove()
    expect(removePermissionGuard).toHaveBeenCalledOnce()
    expect(removeAuthGuard).toHaveBeenCalledOnce()
  })
})
