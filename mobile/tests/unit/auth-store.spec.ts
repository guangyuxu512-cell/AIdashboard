import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import {
  ACTIVE_TEAM_STORAGE_PREFIX,
  configureAuthEffects,
  useAuthStore,
} from '@/app/stores/auth'
import type {
  CurrentModuleAccess,
  CurrentHumanUser,
  HumanAuthDataSource,
  HumanTeamMembership,
} from '@/entities/human-auth'
import { ApiClientError } from '@/shared/api'

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

function createDataSource(
  options: {
    teams?: HumanTeamMembership[]
    moduleAccess?: CurrentModuleAccess
    currentUserError?: unknown
  } = {},
): HumanAuthDataSource {
  return {
    login: vi.fn().mockResolvedValue(user),
    logout: vi.fn().mockResolvedValue(undefined),
    getCurrentUser: options.currentUserError
      ? vi.fn().mockRejectedValue(options.currentUserError)
      : vi.fn().mockResolvedValue(user),
    listMyTeams: vi
      .fn()
      .mockResolvedValue(options.teams ?? [team('team-1', '默认团队')]),
    getCurrentModuleAccess: vi.fn().mockResolvedValue(
      options.moduleAccess ?? {
        moduleCodes: ['device', 'task'],
        isAccessAdministrator: false,
      },
    ),
  }
}

describe('Mobile Human Auth Store', () => {
  beforeEach(() => {
    window.localStorage.clear()
    setActivePinia(createPinia())
    configureAuthEffects({
      onTeamChanged: () => undefined,
      onAuthCleared: () => undefined,
    })
  })

  it('restores the server session, selects the only team and loads module access', async () => {
    const auth = useAuthStore()
    auth.setDataSource(createDataSource())

    await auth.initialize()

    expect(auth.isAuthenticated).toBe(true)
    expect(auth.currentUser).toEqual(user)
    expect(auth.activeTeamId).toBe('team-1')
    expect(auth.currentTeam?.teamName).toBe('默认团队')
    expect(auth.allowedModuleCodes).toEqual(new Set(['device', 'task']))
  })

  it('requires explicit selection for multiple active teams and reuses X-Team-ID state', async () => {
    const onTeamChanged = vi.fn()
    configureAuthEffects({ onTeamChanged })
    const source = createDataSource({
      teams: [team('team-1', '默认团队'), team('team-2', '运营团队')],
    })
    const auth = useAuthStore()
    auth.setDataSource(source)

    await auth.initialize()
    expect(auth.requiresTeamSelection).toBe(true)
    expect(source.getCurrentModuleAccess).not.toHaveBeenCalled()

    await auth.selectTeam('team-2')

    expect(auth.currentTeam?.teamName).toBe('运营团队')
    expect(auth.requiresTeamSelection).toBe(false)
    expect(onTeamChanged).toHaveBeenCalledOnce()
    expect(source.getCurrentModuleAccess).toHaveBeenCalledOnce()
    expect(
      window.localStorage.getItem(
        `${ACTIVE_TEAM_STORAGE_PREFIX}.${user.userId}`,
      ),
    ).toBe('team-2')
  })

  it('does not trust a persisted team that is no longer active', async () => {
    window.localStorage.setItem(
      `${ACTIVE_TEAM_STORAGE_PREFIX}.${user.userId}`,
      'removed-team',
    )
    const auth = useAuthStore()
    auth.setDataSource(
      createDataSource({
        teams: [team('team-1', '默认团队'), team('team-2', '运营团队')],
      }),
    )

    await auth.initialize()

    expect(auth.activeTeamId).toBeNull()
    expect(auth.requiresTeamSelection).toBe(true)
  })

  it('treats missing or invalid Human Session as anonymous', async () => {
    const auth = useAuthStore()
    auth.setDataSource(
      createDataSource({
        currentUserError: new ApiClientError({
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
  })

  it('restores a valid session without persisting an isLoggedIn flag', async () => {
    const auth = useAuthStore()
    auth.setDataSource(createDataSource())

    await auth.initialize()

    expect(Object.keys(window.localStorage)).toEqual([
      `${ACTIVE_TEAM_STORAGE_PREFIX}.${user.userId}`,
    ])
  })

  it('calls Backend logout before clearing user, team and cached access state', async () => {
    const onAuthCleared = vi.fn()
    configureAuthEffects({ onAuthCleared })
    const source = createDataSource()
    const auth = useAuthStore()
    auth.setDataSource(source)
    await auth.initialize()

    await auth.logout()

    expect(source.logout).toHaveBeenCalledOnce()
    expect(auth.status).toBe('anonymous')
    expect(auth.currentUser).toBeNull()
    expect(auth.activeTeamId).toBeNull()
    expect(auth.allowedModuleCodes.size).toBe(0)
    expect(onAuthCleared).toHaveBeenCalledOnce()
    expect(
      window.localStorage.getItem(
        `${ACTIVE_TEAM_STORAGE_PREFIX}.${user.userId}`,
      ),
    ).toBeNull()
  })

  it('keeps the authenticated state when Backend did not confirm logout', async () => {
    const source = createDataSource()
    vi.mocked(source.logout).mockRejectedValueOnce(new Error('network'))
    const auth = useAuthStore()
    auth.setDataSource(source)
    await auth.initialize()

    await expect(auth.logout()).rejects.toThrow('network')
    expect(auth.isAuthenticated).toBe(true)
  })

  it('clears the selected team when the formal Human Session expires', async () => {
    const auth = useAuthStore()
    auth.setDataSource(createDataSource())
    await auth.initialize()

    auth.expireSession()

    expect(auth.status).toBe('anonymous')
    expect(auth.activeTeamId).toBeNull()
    expect(
      window.localStorage.getItem(
        `${ACTIVE_TEAM_STORAGE_PREFIX}.${user.userId}`,
      ),
    ).toBeNull()
  })
})
