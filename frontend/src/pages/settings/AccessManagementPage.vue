<script setup lang="ts">
import { h } from 'vue'
import type { DataTableColumns } from 'naive-ui'
import { Plus } from '@lucide/vue'
import { useDialog } from 'naive-ui'

import type { AccessTeamViewModel } from '@/entities/access-management'
import {
  AccessMemberDrawer,
  AccessMemberFormDialog,
  AccessMemberListTable,
  AccessMembershipFormDialog,
  AccessPasswordResetDialog,
  AccessTeamAuthorizationDialog,
  AccessTeamFormDialog,
  useAccessManagement,
} from '@/features/access-management'
import SettingsLayout from '@/features/system-settings/ui/SettingsLayout.vue'
import ContextSwitchBar from '@/shared/components/ContextSwitchBar.vue'
import DataTable from '@/shared/components/DataTable.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import TableToolbar from '@/shared/components/TableToolbar.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import { useAutoSearch } from '@/shared/composables/useAutoSearch'

const management = useAccessManagement()
const dialog = useDialog()
const autoSearch = useAutoSearch(management.query)

function resetSearch(): void {
  autoSearch.cancel()
  management.reset()
}

const managementTabs = [
  { key: 'members', label: '成员管理' },
  { key: 'teams', label: '团队管理' },
]

function editTeam(team: AccessTeamViewModel): void {
  management.selectedTeam.value = team
  management.teamFormVisible.value = true
}

function confirmArchiveTeam(team: AccessTeamViewModel): void {
  dialog.warning({
    title: '归档团队',
    content: `归档“${team.name}”后，当前成员将失去该团队权限；历史业务数据会保留。`,
    positiveText: '确认归档',
    negativeText: '取消',
    onPositiveClick: () => management.archiveTeam(team),
  })
}

function confirmDeleteTeam(team: AccessTeamViewModel): void {
  dialog.warning({
    title: '删除空团队',
    content: `只有没有成员、授权资源和业务引用的空团队才能删除“${team.name}”。删除不会影响其他团队。`,
    positiveText: '确认删除',
    negativeText: '取消',
    onPositiveClick: () => management.deleteTeam(team),
  })
}

const teamColumns: DataTableColumns<AccessTeamViewModel> = [
  {
    title: '团队名称',
    key: 'name',
    minWidth: 240,
    fixed: 'left',
    ellipsis: { tooltip: true },
  },
  {
    title: '状态',
    key: 'enabled',
    width: 112,
    align: 'center',
    render: (team) =>
      h(StatusTag, {
        label: team.enabled ? '已启用' : '已归档',
        tone: team.enabled ? 'success' : 'neutral',
      }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 268,
    fixed: 'right',
    align: 'center',
    render: (team) =>
      h('div', { class: 'access-management-page__team-actions' }, [
        h(
          AppButton,
          {
            tone: 'text',
            disabled: !team.enabled,
            onClick: () => management.openTeamAuthorization(team),
          },
          () => '团队授权',
        ),
        h(
          AppButton,
          { tone: 'text', onClick: () => editTeam(team) },
          () => '编辑',
        ),
        team.enabled
          ? h(
              AppButton,
              { tone: 'text', onClick: () => confirmArchiveTeam(team) },
              () => '归档',
            )
          : h(
              AppButton,
              { tone: 'text', onClick: () => confirmDeleteTeam(team) },
              () => '删除',
            ),
      ]),
  },
]

function selectTab(key: string): void {
  if (key === 'members' || key === 'teams') management.activeTab.value = key
}

function openCreateTeam(): void {
  management.selectedTeam.value = null
  management.teamFormVisible.value = true
}

function removeMemberFromTeam(): void {
  void management.saveMemberTeam({ teamId: null })
}
</script>

<template>
  <SettingsLayout>
    <div class="access-management-page">
      <TableToolbar class="access-management-page__toolbar">
        <ContextSwitchBar
          appearance="bare"
          :items="managementTabs"
          :active-key="management.activeTab.value"
          label="成员与团队管理"
          @select="selectTab"
        />
        <template #actions>
          <template v-if="management.activeTab.value === 'members'">
            <AppInput
              v-model="management.searchDraft.value"
              aria-label="成员搜索"
              placeholder="搜索显示名或登录账号"
              width="lg"
              clearable
              @update:model-value="autoSearch.onInput"
              @compositionstart="autoSearch.onCompositionStart"
              @compositionend="autoSearch.onCompositionEnd(management.searchDraft.value)"
              @keyup.enter="autoSearch.onEnter($event)"
            />
            <AppButton @click="resetSearch">重置</AppButton>
            <AppButton
              tone="primary"
              @click="management.memberFormVisible.value = true"
            >
              <Plus :size="16" />
              新增成员
            </AppButton>
          </template>
          <AppButton v-else tone="primary" @click="openCreateTeam">
            <Plus :size="16" />
            新增团队
          </AppButton>
        </template>
      </TableToolbar>

      <div
        v-if="management.activeTab.value === 'members'"
        class="access-management-page__table"
      >
        <AccessMemberListTable
          :rows="management.members.value"
          :loading="management.membersLoading.value"
          :error="management.membersError.value"
          :toggling-user-id="management.togglingUserId.value"
          @view="management.openMember"
          @toggle-enabled="management.toggleMemberEnabled"
          @retry="management.retryMembers"
        />
        <PaginationBar
          v-model:page="management.page.value"
          :page-size="management.pageSize.value"
          :item-count="management.total.value"
          @update:page-size="management.setPageSize"
        />
      </div>

      <div v-else class="access-management-page__table">
        <DataTable
          :columns="teamColumns"
          :data="management.teams.value"
          :loading="management.teamsLoading.value"
          viewport="fill"
          appearance="list"
          empty-description="暂无团队"
          @retry="management.retryTeams"
        />
      </div>

      <AccessMemberFormDialog
        :show="management.memberFormVisible.value"
        :teams="management.teams.value"
        :submitting="management.createMemberPending.value"
        @update:show="management.memberFormVisible.value = $event"
        @save="management.createMember"
      />
      <AccessMemberDrawer
        :show="Boolean(management.selectedMember.value)"
        :member="management.selectedMember.value"
        :status-changing="Boolean(management.togglingUserId.value)"
        :team-changing="management.memberTeamPending.value"
        @update:show="!$event && (management.selectedMember.value = null)"
        @toggle-enabled="management.toggleMemberEnabled"
        @reset-password="management.passwordFormVisible.value = true"
        @move-team="management.openMoveMember"
        @remove-team="removeMemberFromTeam"
      />
      <AccessMembershipFormDialog
        :show="management.membershipFormVisible.value"
        :member="management.selectedMember.value"
        :teams="management.teams.value"
        :submitting="management.memberTeamPending.value"
        @update:show="management.membershipFormVisible.value = $event"
        @save="management.saveMemberTeam"
      />
      <AccessPasswordResetDialog
        :show="management.passwordFormVisible.value"
        :submitting="management.passwordPending.value"
        @update:show="management.passwordFormVisible.value = $event"
        @save="management.resetPassword"
      />
      <AccessTeamFormDialog
        :show="management.teamFormVisible.value"
        :team="management.selectedTeam.value"
        :submitting="management.teamPending.value"
        @update:show="management.teamFormVisible.value = $event"
        @save="management.saveTeam"
      />
      <AccessTeamAuthorizationDialog
        :show="management.teamAuthorizationVisible.value"
        :team="management.selectedTeam.value"
        :submitting="management.authorizationPending.value"
        @update:show="management.teamAuthorizationVisible.value = $event"
        @save="management.saveTeamAuthorization"
      />
    </div>
  </SettingsLayout>
</template>

<style scoped>
.access-management-page {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  gap: var(--space-3);
}

.access-management-page__toolbar {
  flex-wrap: nowrap;
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
}

.access-management-page__toolbar :deep(.table-toolbar__actions) {
  margin-left: auto;
  flex-wrap: nowrap;
}

:deep(.access-management-page__team-actions) {
  display: flex;
  justify-content: center;
  gap: var(--space-1);
  white-space: nowrap;
}

@media (max-width: 1200px) {
  .access-management-page__toolbar {
    flex-wrap: wrap;
  }

  .access-management-page__toolbar :deep(.table-toolbar__actions) {
    flex: 1 1 100%;
    margin-left: 0;
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}

.access-management-page__table {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: var(--space-3);
}
</style>
