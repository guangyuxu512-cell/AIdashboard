export interface CurrentHumanUser {
  userId: string
  displayName: string
}

export type DataScope = 'self' | 'team' | 'all'

export interface HumanTeamMembership {
  membershipId: string
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
