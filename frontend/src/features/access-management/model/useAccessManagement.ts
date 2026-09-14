import { computed, ref } from 'vue'
import { useMessage } from 'naive-ui'

import {
  useAccessMembersQuery,
  useAccessTeamsQuery,
  useCreateAccessMemberMutation,
  useCreateAccessMembershipMutation,
  useCreateAccessTeamMutation,
  useResetAccessMemberPasswordMutation,
  useUpdateAccessMemberEnabledMutation,
  useUpdateAccessMembershipMutation,
  useUpdateAccessTeamMutation,
  type AccessMemberCreateInput,
  type AccessMemberViewModel,
  type AccessMembershipInput,
  type AccessMembershipUpdateInput,
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
  const editingMembershipId = ref<string | null>(null)

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
  const createMembershipMutation = useCreateAccessMembershipMutation()
  const updateMembershipMutation = useUpdateAccessMembershipMutation()
  const createTeamMutation = useCreateAccessTeamMutation()
  const updateTeamMutation = useUpdateAccessTeamMutation()

  const members = computed(() => membersQuery.data.value?.items ?? [])
  const teams = computed(() => teamsQuery.data.value ?? [])
  const currentMembership = computed(
    () =>
      selectedMember.value?.memberships.find(
        (membership) => membership.membershipId === editingMembershipId.value,
      ) ?? null,
  )
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

  function openCreateMembership(member: AccessMemberViewModel): void {
    selectedMember.value = member
    editingMembershipId.value = null
    membershipFormVisible.value = true
  }

  function openEditMembership(membershipId: string): void {
    editingMembershipId.value = membershipId
    membershipFormVisible.value = true
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
      message.success(updated.enabled ? '员工已启用' : '员工已停用')
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

  async function saveMembership(input: AccessMembershipInput): Promise<void> {
    if (!selectedMember.value) return
    try {
      const updated = editingMembershipId.value
        ? await updateMembershipMutation.mutateAsync({
            membershipId: editingMembershipId.value,
            input: input as AccessMembershipUpdateInput,
          })
        : await createMembershipMutation.mutateAsync({
            userId: selectedMember.value.userId,
            input,
          })
      selectedMember.value = updated
      membershipFormVisible.value = false
      message.success('团队关系已保存')
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
    currentMembership,
    memberFormVisible,
    membershipFormVisible,
    passwordFormVisible,
    teamFormVisible,
    createMemberPending: createMemberMutation.isPending,
    membershipPending: computed(
      () =>
        createMembershipMutation.isPending.value ||
        updateMembershipMutation.isPending.value,
    ),
    passwordPending: resetPasswordMutation.isPending,
    teamPending: computed(
      () =>
        createTeamMutation.isPending.value ||
        updateTeamMutation.isPending.value,
    ),
    togglingUserId: computed(() =>
      updateMemberEnabledMutation.isPending.value
        ? (updateMemberEnabledMutation.variables.value?.userId ?? null)
        : null,
    ),
    query,
    reset,
    setPageSize,
    openMember,
    openCreateMembership,
    openEditMembership,
    createMember,
    toggleMemberEnabled,
    resetPassword,
    saveMembership,
    saveTeam,
    retryMembers: membersQuery.refetch,
    retryTeams: teamsQuery.refetch,
  }
}
