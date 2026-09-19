import { apiMode, type ApiMode, type PageResult } from '@/shared/api'

import type {
  AccessMemberCreateInput,
  AccessMemberTeamInput,
  AccessMemberViewModel,
  AccessMembershipInput,
  AccessMembershipUpdateInput,
  AccessTeamInput,
  AccessTeamAuthorizationInput,
  AccessTeamAuthorizationViewModel,
  AccessTeamViewModel,
} from '../model/types'
import { accessManagementApi } from './access-management-api'
import type {
  AccessMemberCreateDto,
  AccessMemberReadDto,
  AccessMemberTeamWriteDto,
  AccessMembershipUpdateDto,
  AccessMembershipWriteDto,
  AccessTeamReadDto,
  AccessTeamAuthorizationReadDto,
  AccessTeamAuthorizationWriteDto,
  AccessTeamWriteDto,
} from './contracts'

export interface AccessMemberListParams {
  page: number
  pageSize: number
  search: string
}

export interface AccessManagementDataSource {
  readonly mode: ApiMode
  listMembers(
    params: AccessMemberListParams,
  ): Promise<PageResult<AccessMemberViewModel>>
  createMember(input: AccessMemberCreateInput): Promise<AccessMemberViewModel>
  updateMemberEnabled(
    userId: string,
    enabled: boolean,
  ): Promise<AccessMemberViewModel>
  resetMemberPassword(
    userId: string,
    password: string,
  ): Promise<AccessMemberViewModel>
  moveMemberToTeam(
    userId: string,
    input: AccessMemberTeamInput,
  ): Promise<AccessMemberViewModel>
  createMembership(
    userId: string,
    input: AccessMembershipInput,
  ): Promise<AccessMemberViewModel>
  updateMembership(
    membershipId: string,
    input: AccessMembershipUpdateInput,
  ): Promise<AccessMemberViewModel>
  listTeams(): Promise<AccessTeamViewModel[]>
  createTeam(input: AccessTeamInput): Promise<AccessTeamViewModel>
  updateTeam(
    teamId: string,
    input: AccessTeamInput,
  ): Promise<AccessTeamViewModel>
  archiveTeam(teamId: string): Promise<AccessTeamViewModel>
  deleteTeam(teamId: string): Promise<void>
  getTeamAuthorization(
    teamId: string,
  ): Promise<AccessTeamAuthorizationViewModel>
  updateTeamAuthorization(
    teamId: string,
    input: AccessTeamAuthorizationInput,
  ): Promise<AccessTeamAuthorizationViewModel>
}

function mapMember(dto: AccessMemberReadDto): AccessMemberViewModel {
  return {
    userId: dto.user_id,
    displayName: dto.display_name,
    loginName: dto.login_name,
    enabled: dto.enabled,
    isSuperAccount: dto.is_super_account,
    memberships: dto.memberships.map((membership) => ({
      membershipId: membership.membership_id,
      teamId: membership.team_id,
      teamName: membership.team_name,
      teamEnabled: membership.team_enabled,
      roleCode: membership.role_code,
      dataScope: membership.data_scope,
      enabled: membership.enabled,
      moduleCodes: [...membership.module_codes],
    })),
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}

function mapTeam(dto: AccessTeamReadDto): AccessTeamViewModel {
  return {
    teamId: dto.team_id,
    name: dto.name,
    enabled: dto.enabled,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}

function mapTeamAuthorization(
  dto: AccessTeamAuthorizationReadDto,
): AccessTeamAuthorizationViewModel {
  return {
    teamId: dto.team_id,
    moduleCodes: [...dto.module_codes],
    deviceIds: [...dto.device_ids],
    shopIds: [...dto.shop_ids],
  }
}

function mapMembership(input: AccessMembershipInput): AccessMembershipWriteDto {
  return {
    team_id: input.teamId,
    role_code: input.roleCode,
    data_scope: input.dataScope,
    enabled: input.enabled,
    module_codes: [...input.moduleCodes],
  }
}

function mapMemberCreate(input: AccessMemberCreateInput): AccessMemberCreateDto {
  return {
    display_name: input.displayName.trim(),
    login_name: input.loginName.trim().toLowerCase(),
    password: input.password,
    team_id: input.teamId,
  }
}

function mapMemberTeam(
  input: AccessMemberTeamInput,
): AccessMemberTeamWriteDto {
  return { team_id: input.teamId }
}

function mapMembershipUpdate(
  input: AccessMembershipUpdateInput,
): AccessMembershipUpdateDto {
  return {
    ...(input.roleCode === undefined ? {} : { role_code: input.roleCode }),
    ...(input.dataScope === undefined ? {} : { data_scope: input.dataScope }),
    ...(input.enabled === undefined ? {} : { enabled: input.enabled }),
    ...(input.moduleCodes === undefined
      ? {}
      : { module_codes: [...input.moduleCodes] }),
  }
}

function mapTeamWrite(input: AccessTeamInput): AccessTeamWriteDto {
  return { name: input.name.trim(), enabled: input.enabled }
}

function mapTeamAuthorizationWrite(
  input: AccessTeamAuthorizationInput,
): AccessTeamAuthorizationWriteDto {
  return {
    module_codes: [...input.moduleCodes],
    device_ids: [...input.deviceIds],
    shop_ids: [...input.shopIds],
  }
}

function createMockDataSource(): AccessManagementDataSource {
  const now = new Date().toISOString()
  const teams: AccessTeamViewModel[] = [
    {
      teamId: 'access-team-default',
      name: '默认团队',
      enabled: true,
      createdAt: now,
      updatedAt: now,
    },
  ]
  const authorizations = new Map<string, AccessTeamAuthorizationViewModel>()
  const members: AccessMemberViewModel[] = [
    {
      userId: 'access-user-admin',
      displayName: '系统管理员',
      loginName: 'admin',
      enabled: true,
      isSuperAccount: true,
      memberships: [],
      createdAt: now,
      updatedAt: now,
    },
  ]

  const findMember = (userId: string): AccessMemberViewModel => {
    const member = members.find((item) => item.userId === userId)
    if (!member) throw new Error('员工不存在')
    return member
  }
  const copyMember = (
    member: AccessMemberViewModel,
  ): AccessMemberViewModel => ({
    ...member,
    memberships: member.memberships.map((membership) => ({
      ...membership,
      moduleCodes: [...membership.moduleCodes],
    })),
  })

  return {
    mode: 'mock',
    async listMembers(params) {
      const keyword = params.search.trim().toLowerCase()
      const filtered = members.filter(
        (member) =>
          !keyword ||
          member.displayName.toLowerCase().includes(keyword) ||
          member.loginName?.toLowerCase().includes(keyword),
      )
      const start = (params.page - 1) * params.pageSize
      return {
        items: filtered.slice(start, start + params.pageSize).map(copyMember),
        total: filtered.length,
        page: params.page,
        pageSize: params.pageSize,
      }
    },
    async createMember(input) {
      if (members.some((member) => member.loginName === input.loginName)) {
        throw new Error('登录账号已被使用')
      }
      const team = input.teamId
        ? teams.find((item) => item.teamId === input.teamId)
        : null
      if (input.teamId && !team?.enabled) throw new Error('团队已停用')
      const timestamp = new Date().toISOString()
      const member: AccessMemberViewModel = {
        userId: crypto.randomUUID(),
        displayName: input.displayName.trim(),
        loginName: input.loginName.trim().toLowerCase(),
        enabled: true,
        isSuperAccount: false,
        memberships: team
          ? [
          {
            membershipId: crypto.randomUUID(),
            teamId: team.teamId,
            teamName: team.name,
            teamEnabled: team.enabled,
            roleCode: 'member',
            dataScope: 'team',
            enabled: true,
            moduleCodes: [...(authorizations.get(team.teamId)?.moduleCodes ?? [])],
          },
            ]
          : [],
        createdAt: timestamp,
        updatedAt: timestamp,
      }
      members.unshift(member)
      return copyMember(member)
    },
    async updateMemberEnabled(userId, enabled) {
      const member = findMember(userId)
      member.enabled = enabled
      member.updatedAt = new Date().toISOString()
      return copyMember(member)
    },
    async resetMemberPassword(userId) {
      return copyMember(findMember(userId))
    },
    async moveMemberToTeam(userId, input) {
      const member = findMember(userId)
      if (member.isSuperAccount) throw new Error('超级账号不加入业务团队')
      for (const membership of member.memberships) membership.enabled = false
      if (input.teamId) {
        const team = teams.find((item) => item.teamId === input.teamId)
        if (!team?.enabled) throw new Error('团队已停用')
        const existing = member.memberships.find(
          (item) => item.teamId === input.teamId,
        )
        if (existing) {
          existing.enabled = true
          existing.teamEnabled = team.enabled
          existing.teamName = team.name
        } else {
          member.memberships.push({
            membershipId: crypto.randomUUID(),
            teamId: team.teamId,
            teamName: team.name,
            teamEnabled: team.enabled,
            roleCode: 'member',
            dataScope: 'team',
            enabled: true,
            moduleCodes: [
              ...(authorizations.get(team.teamId)?.moduleCodes ?? []),
            ],
          })
        }
      }
      member.updatedAt = new Date().toISOString()
      return copyMember(member)
    },
    async createMembership(userId, input) {
      const member = findMember(userId)
      const team = teams.find((item) => item.teamId === input.teamId)
      if (!team?.enabled) throw new Error('团队已停用')
      if (member.memberships.some((item) => item.teamId === input.teamId)) {
        throw new Error('用户已加入该团队')
      }
      member.memberships.push({
        membershipId: crypto.randomUUID(),
        teamId: team.teamId,
        teamName: team.name,
        teamEnabled: team.enabled,
        roleCode: input.roleCode,
        dataScope: input.dataScope,
        enabled: input.enabled,
        moduleCodes: [...input.moduleCodes],
      })
      member.updatedAt = new Date().toISOString()
      return copyMember(member)
    },
    async updateMembership(membershipId, input) {
      const member = members.find((item) =>
        item.memberships.some(
          (membership) => membership.membershipId === membershipId,
        ),
      )
      const membership = member?.memberships.find(
        (item) => item.membershipId === membershipId,
      )
      if (!member || !membership) throw new Error('团队成员关系不存在')
      Object.assign(membership, {
        ...(input.roleCode === undefined ? {} : { roleCode: input.roleCode }),
        ...(input.dataScope === undefined
          ? {}
          : { dataScope: input.dataScope }),
        ...(input.enabled === undefined ? {} : { enabled: input.enabled }),
        ...(input.moduleCodes === undefined
          ? {}
          : { moduleCodes: [...input.moduleCodes] }),
      })
      member.updatedAt = new Date().toISOString()
      return copyMember(member)
    },
    async listTeams() {
      return teams.map((team) => ({ ...team }))
    },
    async createTeam(input) {
      const timestamp = new Date().toISOString()
      const team: AccessTeamViewModel = {
        teamId: crypto.randomUUID(),
        name: input.name.trim(),
        enabled: input.enabled,
        createdAt: timestamp,
        updatedAt: timestamp,
      }
      teams.push(team)
      return { ...team }
    },
    async updateTeam(teamId, input) {
      const team = teams.find((item) => item.teamId === teamId)
      if (!team) throw new Error('团队不存在')
      team.name = input.name.trim()
      team.enabled = input.enabled
      team.updatedAt = new Date().toISOString()
      for (const member of members) {
        for (const membership of member.memberships) {
          if (membership.teamId === teamId) {
            membership.teamName = team.name
            membership.teamEnabled = team.enabled
          }
        }
      }
      return { ...team }
    },
    async archiveTeam(teamId) {
      const team = teams.find((item) => item.teamId === teamId)
      if (!team) throw new Error('团队不存在')
      team.enabled = false
      team.updatedAt = new Date().toISOString()
      for (const member of members) {
        for (const membership of member.memberships) {
          if (membership.teamId === teamId) membership.enabled = false
        }
      }
      return { ...team }
    },
    async deleteTeam(teamId) {
      const index = teams.findIndex((item) => item.teamId === teamId)
      if (index < 0) throw new Error('团队不存在')
      if (members.some((member) => member.memberships.some((item) => item.teamId === teamId))) {
        throw new Error('团队仍有关联成员，只能归档')
      }
      teams.splice(index, 1)
      authorizations.delete(teamId)
    },
    async getTeamAuthorization(teamId) {
      if (!teams.some((item) => item.teamId === teamId)) throw new Error('团队不存在')
      return {
        teamId,
        moduleCodes: [...(authorizations.get(teamId)?.moduleCodes ?? [])],
        deviceIds: [...(authorizations.get(teamId)?.deviceIds ?? [])],
        shopIds: [...(authorizations.get(teamId)?.shopIds ?? [])],
      }
    },
    async updateTeamAuthorization(teamId, input) {
      if (!teams.some((item) => item.teamId === teamId)) throw new Error('团队不存在')
      const authorization = {
        teamId,
        moduleCodes: [...input.moduleCodes],
        deviceIds: [...input.deviceIds],
        shopIds: [...input.shopIds],
      }
      authorizations.set(teamId, authorization)
      for (const member of members) {
        for (const membership of member.memberships) {
          if (membership.teamId === teamId) {
            membership.moduleCodes = [...authorization.moduleCodes]
          }
        }
      }
      return authorization
    },
  }
}

const realDataSource: AccessManagementDataSource = {
  mode: 'real',
  async listMembers(params) {
    const page = await accessManagementApi.listMembers(params)
    return {
      items: page.items.map(mapMember),
      total: page.total,
      page: page.page,
      pageSize: page.page_size,
    }
  },
  async createMember(input) {
    return mapMember(
      await accessManagementApi.createMember(mapMemberCreate(input)),
    )
  },
  async updateMemberEnabled(userId, enabled) {
    return mapMember(
      await accessManagementApi.updateMember(userId, { enabled }),
    )
  },
  async resetMemberPassword(userId, password) {
    return mapMember(
      await accessManagementApi.resetMemberPassword(userId, password),
    )
  },
  async moveMemberToTeam(userId, input) {
    return mapMember(
      await accessManagementApi.moveMemberToTeam(
        userId,
        mapMemberTeam(input),
      ),
    )
  },
  async createMembership(userId, input) {
    return mapMember(
      await accessManagementApi.createMembership(userId, mapMembership(input)),
    )
  },
  async updateMembership(membershipId, input) {
    return mapMember(
      await accessManagementApi.updateMembership(
        membershipId,
        mapMembershipUpdate(input),
      ),
    )
  },
  async listTeams() {
    return (await accessManagementApi.listTeams()).map(mapTeam)
  },
  async createTeam(input) {
    return mapTeam(await accessManagementApi.createTeam(mapTeamWrite(input)))
  },
  async updateTeam(teamId, input) {
    return mapTeam(
      await accessManagementApi.updateTeam(teamId, mapTeamWrite(input)),
    )
  },
  async archiveTeam(teamId) {
    return mapTeam(await accessManagementApi.archiveTeam(teamId))
  },
  async deleteTeam(teamId) {
    await accessManagementApi.deleteTeam(teamId)
  },
  async getTeamAuthorization(teamId) {
    return mapTeamAuthorization(
      await accessManagementApi.getTeamAuthorization(teamId),
    )
  },
  async updateTeamAuthorization(teamId, input) {
    return mapTeamAuthorization(
      await accessManagementApi.updateTeamAuthorization(
        teamId,
        mapTeamAuthorizationWrite(input),
      ),
    )
  },
}

export function createAccessManagementDataSource(
  mode: ApiMode,
): AccessManagementDataSource {
  return mode === 'real' ? realDataSource : createMockDataSource()
}

export const accessManagementDataSource =
  createAccessManagementDataSource(apiMode)
