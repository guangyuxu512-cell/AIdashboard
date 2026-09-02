import type { AccessDataScope, AccessRoleCode } from '../model/types'

export interface AccessMembershipReadDto {
  membership_id: string
  team_id: string
  team_name: string
  team_enabled: boolean
  role_code: AccessRoleCode
  data_scope: AccessDataScope
  enabled: boolean
  module_codes: string[]
}

export interface AccessMemberReadDto {
  user_id: string
  display_name: string
  login_name: string | null
  enabled: boolean
  memberships: AccessMembershipReadDto[]
  created_at: string
  updated_at: string
}

export interface AccessTeamReadDto {
  team_id: string
  name: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface AccessMembershipWriteDto {
  team_id: string
  role_code: AccessRoleCode
  data_scope: AccessDataScope
  enabled: boolean
  module_codes: string[]
}

export interface AccessMemberCreateDto {
  display_name: string
  login_name: string
  password: string
  membership: AccessMembershipWriteDto
}

export interface AccessMembershipUpdateDto {
  role_code?: AccessRoleCode
  data_scope?: AccessDataScope
  enabled?: boolean
  module_codes?: string[]
}

export interface AccessMemberUpdateDto {
  enabled: boolean
}

export interface AccessTeamWriteDto {
  name: string
  enabled: boolean
}
