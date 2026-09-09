import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type {
  CurrentModuleAccess,
  CurrentHumanUser,
  HumanAuthDataSource,
  HumanTeamMembership,
} from '@/entities/human-auth'
import { ApiError } from '@/shared/api'

import {
  ACTIVE_TEAM_STORAGE_PREFIX,
  configureAuthEffects,
  useAuthStore,
} from './auth'

const user: CurrentHumanUser = {
  userId: 'user-1',
  displayName: '测试人员',
}

function team(id: string, name: string): HumanTeamMembership {
  return {
    membershipId: `membership-${id}`,
    teamId: id,
    teamName: name,
    teamEnabled: true,
    roleCode: 'member',
    dataScope: 'team',
    membershipEnabled: true,
  }
}

function dataSource(
  options: {
    currentUser?: CurrentHumanUser
    moduleAccess?: CurrentModuleAccess
    teams?: HumanTeamMembership[]
    error?: unknown
  } = {},
): HumanAuthDataSource {
  const current = options.currentUser ?? user
  const memberships = options.teams ?? [team('team-1', '默认团队')]
  const moduleAccess = options.moduleAccess ?? {
    moduleCodes: ['asset'],
    isAccessAdministrator: false,
  }
  return {
    login: vi.fn().mockResolvedValue(current),
    logout: vi.fn().mockResolvedValue(undefined),
    getCurrentUser: options.error
      ? vi.fn().mockRejectedValue(options.error)
      : vi.fn().mockResolvedValue(current),
    listMyTeams: vi.fn().mockResolvedValue(memberships),
    getCurrentModuleAccess: vi.fn().mockResolvedValue(moduleAccess),
  }
}

describe('Human Auth Store', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setActivePinia(createPinia())
    configureAuthEffects({
      onTeamChanged: () => undefined,
      onAuthCleared: () => undefined,
      onAuthRestoreRejected: () => undefined,
    })
  })

  it('restores the server session and auto-selects one active team', async () => {
    const auth = useAuthStore()
    auth.setDataSource(dataSource())

    await auth.initialize()

    expect(auth.isAuthenticated).toBe(true)
    expect(auth.currentUser).toEqual(user)
    expect(auth.activeTeamId).toBe('team-1')
    expect(auth.currentTeam?.teamName).toBe('默认团队')
    expect(auth.requiresTeamSelection).toBe(false)
    expect(auth.allowedModuleCodes).toEqual(new Set(['asset']))
    expect(auth.isAccessAdministrator).toBe(false)
  })

  it('requires an explicit first selection for multiple teams and persists it', async () => {
    const contextChanged = vi.fn()
    configureAuthEffects({ onTeamChanged: contextChanged })
    const auth = useAuthStore()
    auth.setDataSource(
      dataSource({
        teams: [team('team-1', '默认团队'), team('team-2', '运营团队')],
      }),
    )

    await auth.initialize()
    expect(auth.requiresTeamSelection).toBe(true)

    auth.selectTeam('team-2')

    expect(auth.currentTeam?.teamName).toBe('运营团队')
    expect(auth.requiresTeamSelection).toBe(false)
    expect(contextChanged).toHaveBeenCalledTimes(1)
    expect(
      window.localStorage.getItem(`${ACTIVE_TEAM_STORAGE_PREFIX}.user-1`),
    ).toBe('team-2')
  })

  it('does not trust persisted team ids that are no longer active', async () => {
    window.localStorage.setItem(
      `${ACTIVE_TEAM_STORAGE_PREFIX}.user-1`,
      'removed-team',
    )
    const auth = useAuthStore()
    auth.setDataSource(
      dataSource({
        teams: [team('team-1', '默认团队'), team('team-2', '运营团队')],
      }),
    )

    await auth.initialize()

    expect(auth.activeTeamId).toBeNull()
    expect(auth.requiresTeamSelection).toBe(true)
  })

  it('treats an invalid server session as anonymous without local isLoggedIn state', async () => {
    const restoreRejected = vi.fn()
    configureAuthEffects({ onAuthRestoreRejected: restoreRejected })
    const auth = useAuthStore()
    auth.setDataSource(
      dataSource({
        error: new ApiError({
          code: 'HUMAN_SESSION_INVALID',
          message: '登录会话已失效，请重新登录',
          status: 401,
        }),
      }),
    )

    await auth.initialize()

    expect(auth.status).toBe('anonymous')
    expect(auth.currentUser).toBeNull()
    expect(auth.restoreError).toBeNull()
    expect(restoreRejected).toHaveBeenCalledTimes(1)
  })

  it('treats a missing human session as an expected anonymous state', async () => {
    const auth = useAuthStore()
    auth.setDataSource(
      dataSource({
        error: new ApiError({
          code: 'HUMAN_AUTHENTICATION_REQUIRED',
          message: '需要有效的管理端用户身份',
          status: 401,
        }),
      }),
    )

    await auth.initialize()

    expect(auth.status).toBe('anonymous')
    expect(auth.currentUser).toBeNull()
    expect(auth.restoreError).toBeNull()
  })

  it('clears the current user team preference after a successful logout', async () => {
    const authCleared = vi.fn()
    configureAuthEffects({ onAuthCleared: authCleared })
    const source = dataSource()
    const auth = useAuthStore()
    auth.setDataSource(source)
    await auth.initialize()

    await auth.logout()

    expect(source.logout).toHaveBeenCalledTimes(1)
    expect(auth.status).toBe('anonymous')
    expect(auth.activeTeamId).toBeNull()
    expect(
      window.localStorage.getItem(`${ACTIVE_TEAM_STORAGE_PREFIX}.user-1`),
    ).toBeNull()
    expect(authCleared).toHaveBeenCalledTimes(1)
  })

  it('clears the current user team preference when the session expires', async () => {
    const auth = useAuthStore()
    auth.setDataSource(dataSource())
    await auth.initialize()

    auth.expireSession()

    expect(auth.status).toBe('anonymous')
    expect(auth.activeTeamId).toBeNull()
    expect(
      window.localStorage.getItem(`${ACTIVE_TEAM_STORAGE_PREFIX}.user-1`),
    ).toBeNull()
  })

  it('keeps state when the server did not confirm logout', async () => {
    const source = dataSource()
    vi.mocked(source.logout).mockRejectedValueOnce(new Error('network'))
    const auth = useAuthStore()
    auth.setDataSource(source)
    await auth.initialize()

    await expect(auth.logout()).rejects.toThrow('network')
    expect(auth.isAuthenticated).toBe(true)
  })
})
