import { afterEach, describe, expect, it, vi } from 'vitest'

import { humanAuthDataSource } from '@/entities/human-auth'
import { apiClient } from '@/shared/api'

describe('Mobile Human Auth DataSource', () => {
  afterEach(() => vi.restoreAllMocks())

  it('uses the formal login contract without returning or persisting a token', async () => {
    const post = vi.spyOn(apiClient, 'post').mockResolvedValue({
      data: { user_id: 'user-1', display_name: '测试人员' },
    })

    const result = await humanAuthDataSource.login({
      loginName: 'Operator',
      password: 'correct-password',
    })

    expect(post).toHaveBeenCalledWith('auth/login', {
      login_name: 'Operator',
      password: 'correct-password',
    })
    expect(result).toEqual({ userId: 'user-1', displayName: '测试人员' })
    expect(result).not.toHaveProperty('token')
  })

  it('maps session restore, TeamMembership and Module Access contracts', async () => {
    const get = vi.spyOn(apiClient, 'get')
    get.mockResolvedValueOnce({
      data: { user_id: 'user-1', display_name: '测试人员' },
    })
    get.mockResolvedValueOnce({
      data: [
        {
          membership_id: 'membership-1',
          team_id: 'team-1',
          team_name: '默认团队',
          team_enabled: true,
          role_code: 'member',
          data_scope: 'team',
          membership_enabled: true,
        },
        {
          membership_id: null,
          team_id: 'team-2',
          team_name: '超级账号可见团队',
          team_enabled: true,
          role_code: 'super_account',
          data_scope: 'all',
          membership_enabled: true,
        },
      ],
    })
    get.mockResolvedValueOnce({
      data: {
        module_codes: ['device', 'task'],
        is_access_administrator: false,
      },
    })

    await expect(humanAuthDataSource.getCurrentUser()).resolves.toEqual({
      userId: 'user-1',
      displayName: '测试人员',
    })
    await expect(humanAuthDataSource.listMyTeams()).resolves.toEqual([
      {
        membershipId: 'membership-1',
        teamId: 'team-1',
        teamName: '默认团队',
        teamEnabled: true,
        roleCode: 'member',
        dataScope: 'team',
        membershipEnabled: true,
      },
      {
        membershipId: null,
        teamId: 'team-2',
        teamName: '超级账号可见团队',
        teamEnabled: true,
        roleCode: 'super_account',
        dataScope: 'all',
        membershipEnabled: true,
      },
    ])
    await expect(humanAuthDataSource.getCurrentModuleAccess()).resolves.toEqual(
      {
        moduleCodes: ['device', 'task'],
        isAccessAdministrator: false,
      },
    )
    expect(get.mock.calls.map(([path]) => path)).toEqual([
      'auth/me',
      'access/me/teams',
      'access-management/me/module-access',
    ])
  })

  it('uses the idempotent formal logout endpoint', async () => {
    const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: null })

    await humanAuthDataSource.logout()

    expect(post).toHaveBeenCalledWith('auth/logout')
  })
})
