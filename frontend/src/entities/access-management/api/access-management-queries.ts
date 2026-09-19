import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/vue-query'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import type {
  AccessMemberCreateInput,
  AccessMemberTeamInput,
  AccessMembershipInput,
  AccessMembershipUpdateInput,
  AccessTeamInput,
  AccessTeamAuthorizationInput,
} from '../model/types'
import {
  accessManagementDataSource,
  type AccessMemberListParams,
} from './access-management-data-source'

export const accessManagementQueryKeys = {
  all: ['access-management'] as const,
  members: (params: AccessMemberListParams) =>
    ['access-management', 'members', params] as const,
  teams: ['access-management', 'teams'] as const,
  teamAuthorization: (teamId: string | null) =>
    ['access-management', 'teams', teamId, 'authorization'] as const,
}

export function useAccessMembersQuery(
  params: MaybeRefOrGetter<AccessMemberListParams>,
) {
  return useQuery({
    queryKey: computed(() =>
      accessManagementQueryKeys.members(toValue(params)),
    ),
    queryFn: () => accessManagementDataSource.listMembers(toValue(params)),
    placeholderData: keepPreviousData,
  })
}

export function useAccessTeamsQuery() {
  return useQuery({
    queryKey: accessManagementQueryKeys.teams,
    queryFn: () => accessManagementDataSource.listTeams(),
  })
}

export function useAccessTeamAuthorizationQuery(
  teamId: MaybeRefOrGetter<string | null>,
) {
  return useQuery({
    queryKey: computed(() =>
      accessManagementQueryKeys.teamAuthorization(toValue(teamId)),
    ),
    queryFn: () =>
      accessManagementDataSource.getTeamAuthorization(toValue(teamId)!),
    enabled: computed(() => Boolean(toValue(teamId))),
  })
}

function useAccessMutation<Result, Variables>(
  action: (variables: Variables) => Promise<Result>,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: action,
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: accessManagementQueryKeys.all,
      }),
  })
}

export function useCreateAccessMemberMutation() {
  return useAccessMutation((input: AccessMemberCreateInput) =>
    accessManagementDataSource.createMember(input),
  )
}

export function useUpdateAccessMemberEnabledMutation() {
  return useAccessMutation(
    ({ userId, enabled }: { userId: string; enabled: boolean }) =>
      accessManagementDataSource.updateMemberEnabled(userId, enabled),
  )
}

export function useResetAccessMemberPasswordMutation() {
  return useAccessMutation(
    ({ userId, password }: { userId: string; password: string }) =>
      accessManagementDataSource.resetMemberPassword(userId, password),
  )
}

export function useMoveAccessMemberToTeamMutation() {
  return useAccessMutation(
    ({ userId, input }: { userId: string; input: AccessMemberTeamInput }) =>
      accessManagementDataSource.moveMemberToTeam(userId, input),
  )
}

export function useCreateAccessMembershipMutation() {
  return useAccessMutation(
    ({ userId, input }: { userId: string; input: AccessMembershipInput }) =>
      accessManagementDataSource.createMembership(userId, input),
  )
}

export function useUpdateAccessMembershipMutation() {
  return useAccessMutation(
    ({
      membershipId,
      input,
    }: {
      membershipId: string
      input: AccessMembershipUpdateInput
    }) => accessManagementDataSource.updateMembership(membershipId, input),
  )
}

export function useCreateAccessTeamMutation() {
  return useAccessMutation((input: AccessTeamInput) =>
    accessManagementDataSource.createTeam(input),
  )
}

export function useUpdateAccessTeamMutation() {
  return useAccessMutation(
    ({ teamId, input }: { teamId: string; input: AccessTeamInput }) =>
      accessManagementDataSource.updateTeam(teamId, input),
  )
}

export function useArchiveAccessTeamMutation() {
  return useAccessMutation((teamId: string) =>
    accessManagementDataSource.archiveTeam(teamId),
  )
}

export function useDeleteAccessTeamMutation() {
  return useAccessMutation((teamId: string) =>
    accessManagementDataSource.deleteTeam(teamId),
  )
}

export function useUpdateAccessTeamAuthorizationMutation() {
  return useAccessMutation(
    ({
      teamId,
      input,
    }: {
      teamId: string
      input: AccessTeamAuthorizationInput
    }) => accessManagementDataSource.updateTeamAuthorization(teamId, input),
  )
}
