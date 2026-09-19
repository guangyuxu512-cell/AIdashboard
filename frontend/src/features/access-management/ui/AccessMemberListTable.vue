<script setup lang="ts">
import { h } from 'vue'
import type { DataTableColumns } from 'naive-ui'

import type { AccessMemberViewModel } from '@/entities/access-management'
import DataTable from '@/shared/components/DataTable.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import AppButton from '@/shared/ui/AppButton.vue'

const props = defineProps<{
  rows: AccessMemberViewModel[]
  loading?: boolean
  error?: string | null
  togglingUserId?: string | null
}>()

const emit = defineEmits<{
  view: [member: AccessMemberViewModel]
  'toggle-enabled': [member: AccessMemberViewModel]
  retry: []
}>()

function teamSummary(member: AccessMemberViewModel): string {
  if (member.isSuperAccount) return '全部团队'
  return (
    member.memberships.find(
      (membership) => membership.enabled && membership.teamEnabled,
    )?.teamName ?? '未分配团队'
  )
}

const columns: DataTableColumns<AccessMemberViewModel> = [
  {
    title: '员工',
    key: 'displayName',
    width: 150,
    fixed: 'left',
    ellipsis: { tooltip: true },
  },
  {
    title: '登录账号',
    key: 'loginName',
    width: 170,
    ellipsis: { tooltip: true },
    render: (member) => member.loginName ?? '未配置',
  },
  {
    title: '状态',
    key: 'enabled',
    width: 96,
    align: 'center',
    render: (member) =>
      h(StatusTag, {
        label: member.enabled ? '已启用' : '已停用',
        tone: member.enabled ? 'success' : 'neutral',
      }),
  },
  {
    title: '账号类型',
    key: 'accountType',
    width: 120,
    align: 'center',
    render: (member) =>
      h(StatusTag, {
        label: member.isSuperAccount ? '超级账号' : '普通成员',
        tone: member.isSuperAccount ? 'info' : 'neutral',
      }),
  },
  {
    title: '当前团队',
    key: 'teams',
    width: 200,
    ellipsis: { tooltip: true },
    render: teamSummary,
  },
  {
    title: '操作',
    key: 'actions',
    width: 156,
    align: 'center',
    fixed: 'right',
    render: (member) =>
      h('div', { class: 'access-member-table__actions' }, [
        h(
          AppButton,
          { tone: 'text', onClick: () => emit('view', member) },
          () => '详情',
        ),
        h(
          AppButton,
          {
            tone: 'text',
            loading: props.togglingUserId === member.userId,
            disabled:
              Boolean(props.togglingUserId) &&
              props.togglingUserId !== member.userId,
            onClick: () => emit('toggle-enabled', member),
          },
          () => (member.enabled ? '停用' : '启用'),
        ),
      ]),
  },
]
</script>

<template>
  <DataTable
    class="access-member-table"
    :columns="columns"
    :data="rows"
    :loading="loading"
    :error="error"
    :row-key="(row: AccessMemberViewModel) => row.userId"
    :scroll-x="892"
    appearance="list"
    viewport="fill"
    empty-description="暂无员工"
    @retry="$emit('retry')"
  />
</template>

<style scoped>
.access-member-table {
  min-height: 0;
  flex: 1;
}

:deep(.access-member-table__actions) {
  display: flex;
  justify-content: center;
  gap: var(--space-1);
}
</style>
