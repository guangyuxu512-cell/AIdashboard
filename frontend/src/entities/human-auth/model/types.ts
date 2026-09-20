export interface CurrentHumanUser {
  userId: string
  displayName: string
}

export type DataScope = 'self' | 'team' | 'all'

export interface HumanTeamMembership {
  membershipId: string | null
  teamId: string
  teamName: string
  teamEnabled: boolean
  roleCode: string
  dataScope: DataScope
  membershipEnabled: boolean
}

export interface HumanLoginInput {
  loginName: string
  password: string
}

export interface CurrentModuleAccess {
  moduleCodes: string[]
  isSuperAccount: boolean
  /** @deprecated UI compatibility alias; this is now exactly super-account. */
  isAccessAdministrator: boolean
}
