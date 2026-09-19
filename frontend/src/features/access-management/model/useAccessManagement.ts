import { computed, ref } from 'vue'
import { useMessage } from 'naive-ui'

import {
  useAccessMembersQuery,
  useAccessTeamsQuery,
  useArchiveAccessTeamMutation,
  useCreateAccessMemberMutation,
  useCreateAccessTeamMutation,
  useDeleteAccessTeamMutation,
  useMoveAccessMemberToTeamMutation,
  useResetAccessMemberPasswordMutation,
  useUpdateAccessMemberEnabledMutation,
  useUpdateAccessTeamAuthorizationMutation,
  useUpdateAccessTeamMutation,
  type AccessMemberCreateInput,
  type AccessMemberTeamInput,
  type AccessMemberViewModel,
  type AccessTeamAuthorizationInput,
  type AccessTeamInput,
  type AccessTeamViewModel,
} from '@/entities/access-management'
import { getErrorMessage } from '@/shared/api'

export function useAccessManagement() {
  const message = useMessage()
  const activeTab = ref<'members' | 'teams'>('members')
  const page = ref(1)
  const pageSize = ref(20)
  const searchDraft = ref('')
  const search = ref('')
  const selectedMember = ref<AccessMemberViewModel | null>(null)
  const selectedTeam = ref<AccessTeamViewModel | null>(null)
  const memberFormVisible = ref(false)
  const membershipFormVisible = ref(false)
  const passwordFormVisible = ref(false)
  const teamFormVisible = ref(false)
  const teamAuthorizationVisible = ref(false)

  const membersQuery = useAccessMembersQuery(
    computed(() => ({
      page: page.value,
      pageSize: pageSize.value,
      search: search.value,
    })),
  )
  const teamsQuery = useAccessTeamsQuery()
  const createMemberMutation = useCreateAccessMemberMutation()
  const updateMemberEnabledMutation = useUpdateAccessMemberEnabledMutation()
  const resetPasswordMutation = useResetAccessMemberPasswordMutation()
  const moveMemberMutation = useMoveAccessMemberToTeamMutation()
  const createTeamMutation = useCreateAccessTeamMutation()
  const updateTeamMutation = useUpdateAccessTeamMutation()
  const archiveTeamMutation = useArchiveAccessTeamMutation()
  const deleteTeamMutation = useDeleteAccessTeamMutation()
  const updateAuthorizationMutation =
    useUpdateAccessTeamAuthorizationMutation()

  const members = computed(() => membersQuery.data.value?.items ?? [])
  const teams = computed(() => teamsQuery.data.value ?? [])
  const membersHaveData = computed(() => membersQuery.data.value !== undefined)
  const membersLoading = computed(
    () => membersQuery.isPending.value && !membersHaveData.value,
  )
  const membersError = computed(() =>
    membersQuery.error.value ? getErrorMessage(membersQuery.error.value) : null,
  )

  function query(): void {
    page.value = 1
    search.value = searchDraft.value.trim()
  }

  function reset(): void {
    searchDraft.value = ''
    search.value = ''
    page.value = 1
  }

  function setPageSize(value: number): void {
    pageSize.value = value
    page.value = 1
  }

  function openMember(member: AccessMemberViewModel): void {
    selectedMember.value = member
  }

  function openMoveMember(member: AccessMemberViewModel): void {
    selectedMember.value = member
    membershipFormVisible.value = true
  }

  function openTeamAuthorization(team: AccessTeamViewModel): void {
    selectedTeam.value = team
    teamAuthorizationVisible.value = true
  }

  async function createMember(input: AccessMemberCreateInput): Promise<void> {
    try {
      const member = await createMemberMutation.mutateAsync(input)
      memberFormVisible.value = false
      selectedMember.value = member
      message.success('成员已新增')
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }

  async function toggleMemberEnabled(
    member: AccessMemberViewModel,
  ): Promise<void> {
    try {
      const updated = await updateMemberEnabledMutation.mutateAsync({
        userId: member.userId,
        enabled: !member.enabled,
      })
      selectedMember.value = updated
      message.success(updated.enabled ? '成员已启用' : '成员已停用')
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }

  async function resetPassword(password: string): Promise<void> {
    if (!selectedMember.value) return
    try {
      const updated = await resetPasswordMutation.mutateAsync({
        userId: selectedMember.value.userId,
        password,
      })
      selectedMember.value = updated
      passwordFormVisible.value = false
      message.success('密码已重置，旧会话已失效')
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }

  async function saveMemberTeam(input: AccessMemberTeamInput): Promise<void> {
    if (!selectedMember.value) return
    try {
      const updated = await moveMemberMutation.mutateAsync({
        userId: selectedMember.value.userId,
        input,
      })
      selectedMember.value = updated
      membershipFormVisible.value = false
      message.success(input.teamId ? '成员已调入目标团队' : '成员已移出团队')
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }

  async function saveTeam(input: AccessTeamInput): Promise<void> {
    try {
      if (selectedTeam.value) {
        await updateTeamMutation.mutateAsync({
          teamId: selectedTeam.value.teamId,
          input,
        })
      } else {
        await createTeamMutation.mutateAsync(input)
      }
      teamFormVisible.value = false
      selectedTeam.value = null
      message.success('团队已保存')
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }

  async function archiveTeam(team: AccessTeamViewModel): Promise<void> {
    try {
      await archiveTeamMutation.mutateAsync(team.teamId)
      message.success('团队已归档，成员关系与历史业务数据已保留')
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }

  async function deleteTeam(team: AccessTeamViewModel): Promise<void> {
    try {
      await deleteTeamMutation.mutateAsync(team.teamId)
      message.success('空团队已删除')
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }

  async function saveTeamAuthorization(
    input: AccessTeamAuthorizationInput,
  ): Promise<void> {
    if (!selectedTeam.value) return
    try {
      await updateAuthorizationMutation.mutateAsync({
        teamId: selectedTeam.value.teamId,
        input,
      })
      teamAuthorizationVisible.value = false
      message.success('团队授权已保存')
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }

  return {
    activeTab,
    page,
    pageSize,
    searchDraft,
    members,
    teams,
    total: computed(() => membersQuery.data.value?.total ?? 0),
    membersLoading,
    membersError,
    teamsLoading: teamsQuery.isPending,
    selectedMember,
    selectedTeam,
    memberFormVisible,
    membershipFormVisible,
    passwordFormVisible,
    teamFormVisible,
    teamAuthorizationVisible,
    createMemberPending: createMemberMutation.isPending,
    memberTeamPending: moveMemberMutation.isPending,
    passwordPending: resetPasswordMutation.isPending,
    teamPending: computed(
      () =>
        createTeamMutation.isPending.value || updateTeamMutation.isPending.value,
    ),
    authorizationPending: updateAuthorizationMutation.isPending,
    togglingUserId: computed(() =>
      updateMemberEnabledMutation.isPending.value
        ? (updateMemberEnabledMutation.variables.value?.userId ?? null)
        : null,
    ),
    query,
    reset,
    setPageSize,
    openMember,
    openMoveMember,
    openTeamAuthorization,
    createMember,
    toggleMemberEnabled,
    resetPassword,
    saveMemberTeam,
    saveTeam,
    archiveTeam,
    deleteTeam,
    saveTeamAuthorization,
    retryMembers: membersQuery.refetch,
    retryTeams: teamsQuery.refetch,
  }
}
