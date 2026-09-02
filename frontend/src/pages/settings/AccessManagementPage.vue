<script setup lang="ts">
import { computed, h } from 'vue'
import type { DataTableColumns } from 'naive-ui'
import { Plus } from '@lucide/vue'

import type { AccessTeamViewModel } from '@/entities/access-management'
import { getModuleAccessOptions } from '@/app/modules/registry'
import {
  AccessMemberDrawer,
  AccessMemberFormDialog,
  AccessMemberListTable,
  AccessMembershipFormDialog,
  AccessPasswordResetDialog,
  AccessTeamFormDialog,
  useAccessManagement,
} from '@/features/access-management'
import SystemSettingsNavigation from '@/features/system-settings/ui/SystemSettingsNavigation.vue'
import ContextSwitchBar from '@/shared/components/ContextSwitchBar.vue'
import DataTable from '@/shared/components/DataTable.vue'
import FilterBar from '@/shared/components/FilterBar.vue'
import ManagementListSection from '@/shared/components/ManagementListSection.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppInput from '@/shared/ui/AppInput.vue'

const management = useAccessManagement()
const moduleOptions = getModuleAccessOptions()

const managementTabs = [
  { key: 'members', label: '成员管理' },
  { key: 'teams', label: '团队管理' },
]

const teamColumns: DataTableColumns<AccessTeamViewModel> = [
  {
    title: '团队名称',
    key: 'name',
    minWidth: 220,
    ellipsis: { tooltip: true },
  },
  {
    title: '状态',
    key: 'enabled',
    width: 110,
    align: 'center',
    render: (team) =>
      h(StatusTag, {
        label: team.enabled ? '已启用' : '已停用',
        tone: team.enabled ? 'success' : 'neutral',
      }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    align: 'center',
    render: (team) =>
      h(
        AppButton,
        {
          tone: 'text',
          onClick: () => {
            management.selectedTeam.value = team
            management.teamFormVisible.value = true
          },
        },
        () => '编辑',
      ),
  },
]

const currentMembership = computed(() => management.currentMembership.value)

function selectTab(key: string): void {
  if (key === 'members' || key === 'teams') management.activeTab.value = key
}

function openCreateTeam(): void {
  management.selectedTeam.value = null
  management.teamFormVisible.value = true
}
</script>

<template>
  <div class="page-container access-management-page">
    <SystemSettingsNavigation />
    <ContextSwitchBar
      :items="managementTabs"
      :active-key="management.activeTab.value"
      label="用户与权限"
      @select="selectTab"
    />

    <template v-if="management.activeTab.value === 'members'">
      <FilterBar>
        <AppInput
          v-model="management.searchDraft.value"
          placeholder="搜索显示名或登录账号"
          width="lg"
          clearable
          @keyup.enter="management.query"
        />
        <template #actions>
          <AppButton @click="management.reset">重置</AppButton>
          <AppButton tone="primary" @click="management.query">查询</AppButton>
        </template>
        <template #primary-action>
          <AppButton
            tone="primary"
            @click="management.memberFormVisible.value = true"
          >
            <Plus :size="16" />
            新增成员
          </AppButton>
        </template>
      </FilterBar>

      <ManagementListSection>
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
      </ManagementListSection>
    </template>

    <template v-else>
      <FilterBar>
        <template #primary-action>
          <AppButton tone="primary" @click="openCreateTeam">
            <Plus :size="16" />
            新增团队
          </AppButton>
        </template>
      </FilterBar>
      <ManagementListSection>
        <DataTable
          :columns="teamColumns"
          :data="management.teams.value"
          :loading="management.teamsLoading.value"
          viewport="fill"
          appearance="list"
          empty-description="暂无团队"
          @retry="management.retryTeams"
        />
      </ManagementListSection>
    </template>

    <AccessMemberFormDialog
      :show="management.memberFormVisible.value"
      :teams="management.teams.value"
      :module-options="moduleOptions"
      :submitting="management.createMemberPending.value"
      @update:show="management.memberFormVisible.value = $event"
      @save="management.createMember"
    />
    <AccessMemberDrawer
      :show="Boolean(management.selectedMember.value)"
      :member="management.selectedMember.value"
      :status-changing="Boolean(management.togglingUserId.value)"
      @update:show="!$event && (management.selectedMember.value = null)"
      @toggle-enabled="management.toggleMemberEnabled"
      @reset-password="management.passwordFormVisible.value = true"
      @create-membership="management.openCreateMembership"
      @edit-membership="management.openEditMembership($event.membershipId)"
    />
    <AccessMembershipFormDialog
      :show="management.membershipFormVisible.value"
      :membership="currentMembership"
      :teams="management.teams.value"
      :module-options="moduleOptions"
      :submitting="management.membershipPending.value"
      @update:show="management.membershipFormVisible.value = $event"
      @save="management.saveMembership"
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
  </div>
</template>

<style scoped>
.access-management-page {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  gap: var(--space-4);
}
</style>
