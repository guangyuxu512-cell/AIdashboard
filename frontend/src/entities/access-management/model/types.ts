export type AccessRoleCode = 'member' | 'access_admin'
export type AccessDataScope = 'self' | 'team' | 'all'

export interface AccessMembershipViewModel {
  membershipId: string
  teamId: string
  teamName: string
  teamEnabled: boolean
  roleCode: AccessRoleCode
  dataScope: AccessDataScope
  enabled: boolean
  moduleCodes: string[]
}

export interface AccessMemberViewModel {
  userId: string
  displayName: string
  loginName: string | null
  enabled: boolean
  memberships: AccessMembershipViewModel[]
  createdAt: string
  updatedAt: string
}

export interface AccessTeamViewModel {
  teamId: string
  name: string
  enabled: boolean
  createdAt: string
  updatedAt: string
}

export interface AccessMembershipInput {
  teamId: string
  roleCode: AccessRoleCode
  dataScope: AccessDataScope
  enabled: boolean
  moduleCodes: string[]
}

export interface AccessMemberCreateInput {
  displayName: string
  loginName: string
  password: string
  membership: AccessMembershipInput
}

export interface AccessMembershipUpdateInput {
  roleCode?: AccessRoleCode
  dataScope?: AccessDataScope
  enabled?: boolean
  moduleCodes?: string[]
}

export interface AccessTeamInput {
  name: string
  enabled: boolean
}
