import { afterEach, describe, expect, it, vi } from 'vitest'

import { httpClient } from '@/shared/api'

import { createHumanAuthDataSource } from './human-auth-data-source'

describe('Human Auth Data Source', () => {
  afterEach(() => vi.restoreAllMocks())

  it('maps the real login and current-user contracts without exposing a token', async () => {
    const post = vi.spyOn(httpClient, 'post').mockResolvedValue({
      data: { user_id: 'user-1', display_name: '测试人员' },
    })
    const source = createHumanAuthDataSource('real')

    const result = await source.login({
      loginName: 'Operator',
      password: 'secret',
    })

    expect(post).toHaveBeenCalledWith('/api/v1/auth/login', {
      login_name: 'Operator',
      password: 'secret',
    })
    expect(result).toEqual({ userId: 'user-1', displayName: '测试人员' })
    expect(result).not.toHaveProperty('token')
  })

  it('maps my teams and preserves enabled membership facts', async () => {
    vi.spyOn(httpClient, 'get').mockResolvedValue({
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
      ],
    })
    const source = createHumanAuthDataSource('real')

    await expect(source.listMyTeams()).resolves.toEqual([
      {
        membershipId: 'membership-1',
        teamId: 'team-1',
        teamName: '默认团队',
        teamEnabled: true,
        roleCode: 'member',
        dataScope: 'team',
        membershipEnabled: true,
      },
    ])
  })
})
