import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import type {
  CurrentModuleAccess,
  CurrentHumanUser,
  HumanAuthDataSource,
  HumanTeamMembership,
} from '@/entities/human-auth'
import { useAuthStore } from '@/stores/auth'

import { installAuthGuard } from './auth-guard'
import appRouter from './index'

const user: CurrentHumanUser = {
  userId: 'parameter-preset-route-user',
  displayName: '参数配置路由验收',
}

function createSource(moduleCodes: string[]): HumanAuthDataSource {
  const team: HumanTeamMembership = {
    membershipId: 'parameter-preset-route-membership',
    teamId: 'parameter-preset-route-team',
    teamName: '参数配置路由团队',
    teamEnabled: true,
    membershipEnabled: true,
    roleCode: 'member',
    dataScope: 'team',
  }
  const access: CurrentModuleAccess = {
    moduleCodes,
    isAccessAdministrator: false,
    isSuperAccount: false,
  }
  return {
    login: vi.fn().mockResolvedValue(user),
    logout: vi.fn().mockResolvedValue(undefined),
    getCurrentUser: vi.fn().mockResolvedValue(user),
    listMyTeams: vi.fn().mockResolvedValue([team]),
    getCurrentModuleAccess: vi.fn().mockResolvedValue(access),
  }
}

function createGuardedRouter(pinia: ReturnType<typeof createPinia>) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/login',
        name: 'login',
        component: { template: '<div />' },
        meta: { public: true },
      },
      {
        path: '/permission-denied',
        name: 'permission-denied',
        component: { template: '<div />' },
      },
      {
        path: '/assets',
        name: 'assets',
        component: { template: '<div />' },
        meta: { moduleCode: 'asset' },
      },
    ],
  })
  installAuthGuard(router, pinia)
  return router
}

describe('route authorization', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setActivePinia(createPinia())
  })

  it.each([false, true])(
    'keeps the hidden asset route protected; asset grant=%s',
    async (hasAssetGrant) => {
      const pinia = createPinia()
      useAuthStore(pinia).setDataSource(
        createSource(hasAssetGrant ? ['asset'] : ['shop']),
      )
      const router = createGuardedRouter(pinia)
      await router.push('/assets')
      await router.isReady()
      expect(router.currentRoute.value.name).toBe(
        hasAssetGrant ? 'assets' : 'permission-denied',
      )
    },
  )

  it('does not register retired central shop or Yingdao preset routes', () => {
    const names = appRouter.getRoutes().map((route) => route.name)
    expect(names).not.toContain('shops')
    expect(names).not.toContain('parameter-presets')
    expect(names).not.toContain('product-selection')
  })
})
