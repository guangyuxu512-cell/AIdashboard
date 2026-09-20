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
  is_super_account: boolean
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
  team_id: string | null
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

export interface AccessMemberTeamWriteDto {
  team_id: string | null
}

export interface AccessTeamAuthorizationReadDto {
  team_id: string
  module_codes: string[]
  device_ids: string[]
  shop_ids: string[]
}

export interface AccessTeamAuthorizationWriteDto {
  module_codes: string[]
  device_ids: string[]
  shop_ids: string[]
}
