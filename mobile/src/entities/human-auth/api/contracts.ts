export interface CurrentHumanUserDto {
  user_id: string
  display_name: string
}

export interface HumanTeamMembershipDto {
  membership_id: string
  team_id: string
  team_name: string
  team_enabled: boolean
  role_code: string
  data_scope: 'self' | 'team' | 'all'
  membership_enabled: boolean
}

export interface CurrentModuleAccessDto {
  module_codes: string[]
  is_access_administrator: boolean
}
