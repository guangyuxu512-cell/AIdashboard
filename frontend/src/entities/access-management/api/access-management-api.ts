import { httpClient, type PageDto, type PageParams } from '@/shared/api'

import type {
  AccessMemberCreateDto,
  AccessMemberReadDto,
  AccessMemberUpdateDto,
  AccessMembershipUpdateDto,
  AccessMembershipWriteDto,
  AccessTeamReadDto,
  AccessTeamWriteDto,
} from './contracts'

const basePath = '/api/v1/access-management'

export const accessManagementApi = {
  async listMembers(
    params: PageParams & { search: string },
  ): Promise<PageDto<AccessMemberReadDto>> {
    const response = await httpClient.get<PageDto<AccessMemberReadDto>>(
      `${basePath}/members`,
      {
        params: {
          page: params.page,
          page_size: params.pageSize,
          search: params.search || undefined,
        },
      },
    )
    return response.data
  },
  async createMember(
    data: AccessMemberCreateDto,
  ): Promise<AccessMemberReadDto> {
    const response = await httpClient.post<AccessMemberReadDto>(
      `${basePath}/members`,
      data,
    )
    return response.data
  },
  async updateMember(
    userId: string,
    data: AccessMemberUpdateDto,
  ): Promise<AccessMemberReadDto> {
    const response = await httpClient.patch<AccessMemberReadDto>(
      `${basePath}/members/${userId}`,
      data,
    )
    return response.data
  },
  async resetMemberPassword(
    userId: string,
    password: string,
  ): Promise<AccessMemberReadDto> {
    const response = await httpClient.post<AccessMemberReadDto>(
      `${basePath}/members/${userId}/password`,
      { password },
    )
    return response.data
  },
  async createMembership(
    userId: string,
    data: AccessMembershipWriteDto,
  ): Promise<AccessMemberReadDto> {
    const response = await httpClient.post<AccessMemberReadDto>(
      `${basePath}/members/${userId}/memberships`,
      data,
    )
    return response.data
  },
  async updateMembership(
    membershipId: string,
    data: AccessMembershipUpdateDto,
  ): Promise<AccessMemberReadDto> {
    const response = await httpClient.patch<AccessMemberReadDto>(
      `${basePath}/memberships/${membershipId}`,
      data,
    )
    return response.data
  },
  async listTeams(): Promise<AccessTeamReadDto[]> {
    const response = await httpClient.get<AccessTeamReadDto[]>(
      `${basePath}/teams`,
    )
    return response.data
  },
  async createTeam(data: AccessTeamWriteDto): Promise<AccessTeamReadDto> {
    const response = await httpClient.post<AccessTeamReadDto>(
      `${basePath}/teams`,
      data,
    )
    return response.data
  },
  async updateTeam(
    teamId: string,
    data: AccessTeamWriteDto,
  ): Promise<AccessTeamReadDto> {
    const response = await httpClient.patch<AccessTeamReadDto>(
      `${basePath}/teams/${teamId}`,
      data,
    )
    return response.data
  },
}
