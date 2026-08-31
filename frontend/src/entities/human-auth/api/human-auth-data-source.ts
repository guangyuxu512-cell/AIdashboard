import { apiMode, ApiError, httpClient, type ApiMode } from '@/shared/api'

import type {
  CurrentHumanUser,
  HumanLoginInput,
  HumanTeamMembership,
} from '../model/types'

interface CurrentHumanUserDto {
  user_id: string
  display_name: string
}

interface HumanTeamMembershipDto {
  membership_id: string
  team_id: string
  team_name: string
  team_enabled: boolean
  role_code: string
  data_scope: 'self' | 'team' | 'all'
  membership_enabled: boolean
}

export interface HumanAuthDataSource {
  login(input: HumanLoginInput): Promise<CurrentHumanUser>
  logout(): Promise<void>
  getCurrentUser(): Promise<CurrentHumanUser>
  listMyTeams(): Promise<HumanTeamMembership[]>
}

function mapUser(dto: CurrentHumanUserDto): CurrentHumanUser {
  return { userId: dto.user_id, displayName: dto.display_name }
}

function mapTeam(dto: HumanTeamMembershipDto): HumanTeamMembership {
  return {
    membershipId: dto.membership_id,
    teamId: dto.team_id,
    teamName: dto.team_name,
    teamEnabled: dto.team_enabled,
    roleCode: dto.role_code,
    dataScope: dto.data_scope,
    membershipEnabled: dto.membership_enabled,
  }
}

function createRealHumanAuthDataSource(): HumanAuthDataSource {
  return {
    async login(input) {
      const response = await httpClient.post<CurrentHumanUserDto>(
        '/api/v1/auth/login',
        { login_name: input.loginName, password: input.password },
      )
      return mapUser(response.data)
    },
    async logout() {
      await httpClient.post('/api/v1/auth/logout')
    },
    async getCurrentUser() {
      const response =
        await httpClient.get<CurrentHumanUserDto>('/api/v1/auth/me')
      return mapUser(response.data)
    },
    async listMyTeams() {
      const response = await httpClient.get<HumanTeamMembershipDto[]>(
        '/api/v1/access/me/teams',
      )
      return response.data.map(mapTeam)
    },
  }
}

function createMockHumanAuthDataSource(): HumanAuthDataSource {
  let currentUser: CurrentHumanUser | null = {
    userId: '00000000-0000-4000-8000-000000000001',
    displayName: '开发预览',
  }
  let teams: HumanTeamMembership[] = [
    {
      membershipId: '00000000-0000-4000-8000-000000000011',
      teamId: '00000000-0000-4000-8000-000000000021',
      teamName: '默认团队',
      teamEnabled: true,
      roleCode: 'member',
      dataScope: 'team',
      membershipEnabled: true,
    },
  ]

  const requireUser = (): CurrentHumanUser => {
    if (!currentUser) {
      throw new ApiError({
        code: 'HUMAN_AUTHENTICATION_REQUIRED',
        message: '需要有效的管理端用户身份',
        status: 401,
      })
    }
    return currentUser
  }

  return {
    async login(input) {
      if (!input.loginName.trim() || !input.password) {
        throw new ApiError({
          code: 'HUMAN_LOGIN_FAILED',
          message: '登录账号或密码错误',
          status: 401,
        })
      }
      const multipleTeams = input.loginName
        .trim()
        .toLowerCase()
        .includes('multi')
      currentUser = {
        userId: '00000000-0000-4000-8000-000000000001',
        displayName: multipleTeams ? '多团队测试人员' : '测试人员',
      }
      teams = [
        {
          membershipId: '00000000-0000-4000-8000-000000000011',
          teamId: '00000000-0000-4000-8000-000000000021',
          teamName: '默认团队',
          teamEnabled: true,
          roleCode: 'member',
          dataScope: 'team',
          membershipEnabled: true,
        },
        ...(multipleTeams
          ? [
              {
                membershipId: '00000000-0000-4000-8000-000000000012',
                teamId: '00000000-0000-4000-8000-000000000022',
                teamName: '运营团队',
                teamEnabled: true,
                roleCode: 'member',
                dataScope: 'team' as const,
                membershipEnabled: true,
              },
            ]
          : []),
      ]
      return currentUser
    },
    async logout() {
      currentUser = null
      teams = []
    },
    async getCurrentUser() {
      return requireUser()
    },
    async listMyTeams() {
      requireUser()
      return [...teams]
    },
  }
}

export function createHumanAuthDataSource(mode: ApiMode): HumanAuthDataSource {
  return mode === 'real'
    ? createRealHumanAuthDataSource()
    : createMockHumanAuthDataSource()
}

export const humanAuthDataSource = createHumanAuthDataSource(apiMode)
