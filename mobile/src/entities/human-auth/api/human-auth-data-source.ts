import { apiClient } from '@/shared/api'

import type {
  CurrentModuleAccess,
  CurrentHumanUser,
  HumanLoginInput,
  HumanTeamMembership,
} from '../model/types'
import type {
  CurrentHumanUserDto,
  CurrentModuleAccessDto,
  HumanTeamMembershipDto,
} from './contracts'

export interface HumanAuthDataSource {
  login(input: HumanLoginInput): Promise<CurrentHumanUser>
  logout(): Promise<void>
  getCurrentUser(): Promise<CurrentHumanUser>
  listMyTeams(): Promise<HumanTeamMembership[]>
  getCurrentModuleAccess(): Promise<CurrentModuleAccess>
}

function mapCurrentUser(dto: CurrentHumanUserDto): CurrentHumanUser {
  return {
    userId: dto.user_id,
    displayName: dto.display_name,
  }
}

function mapMembership(dto: HumanTeamMembershipDto): HumanTeamMembership {
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

function mapModuleAccess(dto: CurrentModuleAccessDto): CurrentModuleAccess {
  return {
    moduleCodes: [...dto.module_codes],
    isAccessAdministrator: dto.is_access_administrator,
  }
}

export const humanAuthDataSource: HumanAuthDataSource = {
  async login(input) {
    const response = await apiClient.post<CurrentHumanUserDto>('auth/login', {
      login_name: input.loginName,
      password: input.password,
    })
    return mapCurrentUser(response.data)
  },

  async logout() {
    await apiClient.post('auth/logout')
  },

  async getCurrentUser() {
    const response = await apiClient.get<CurrentHumanUserDto>('auth/me')
    return mapCurrentUser(response.data)
  },

  async listMyTeams() {
    const response =
      await apiClient.get<HumanTeamMembershipDto[]>('access/me/teams')
    return response.data.map(mapMembership)
  },

  async getCurrentModuleAccess() {
    const response = await apiClient.get<CurrentModuleAccessDto>(
      'access-management/me/module-access',
    )
    return mapModuleAccess(response.data)
  },
}
