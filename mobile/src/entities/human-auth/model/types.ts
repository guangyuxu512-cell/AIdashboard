export interface CurrentHumanUser {
  userId: string
  displayName: string
}

export type HumanDataScope = 'self' | 'team' | 'all'

export interface HumanTeamMembership {
  membershipId: string | null
  teamId: string
  teamName: string
  teamEnabled: boolean
  roleCode: string
  dataScope: HumanDataScope
  membershipEnabled: boolean
}

export interface HumanLoginInput {
  loginName: string
  password: string
}

export interface CurrentModuleAccess {
  moduleCodes: string[]
  isAccessAdministrator: boolean
}
