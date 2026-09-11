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
      { path: '/login', name: 'login', component: { template: '<div />' }, meta: { public: true } },
      { path: '/permission-denied', name: 'permission-denied', component: { template: '<div />' } },
      {
        path: '/parameter-presets',
        name: 'parameter-presets',
        component: { template: '<div />' },
        meta: { moduleCode: 'parameter-preset' },
      },
    ],
  })
  installAuthGuard(router, pinia)
  return router
}

describe('parameter preset route authorization', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setActivePinia(createPinia())
  })

  it('allows the distinct route when the existing Device permission is granted', async () => {
    const pinia = createPinia()
    const auth = useAuthStore(pinia)
    auth.setDataSource(createSource(['device']))
    const router = createGuardedRouter(pinia)

    await router.push('/parameter-presets')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('parameter-presets')
  })

  it('does not expose the route without the existing Device permission', async () => {
    const pinia = createPinia()
    const auth = useAuthStore(pinia)
    auth.setDataSource(createSource(['shop']))
    const router = createGuardedRouter(pinia)

    await router.push('/parameter-presets')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('permission-denied')
  })
})
