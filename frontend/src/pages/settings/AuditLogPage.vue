<script setup lang="ts">
import { computed, h, ref } from 'vue'
import type { DataTableColumns, SelectOption } from 'naive-ui'
import dayjs from 'dayjs'

import {
  getAuditActionLabel,
  getAuditSummary,
  getAuditTargetLabel,
  type AuditAction,
  type AuditLogViewModel,
  useAuditLogsQuery,
} from '@/entities/audit-log'
import SettingsLayout from '@/features/system-settings/ui/SettingsLayout.vue'
import DataTable from '@/shared/components/DataTable.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'
import TableToolbar from '@/shared/components/TableToolbar.vue'
import { getErrorMessage } from '@/shared/api'
import AppButton from '@/shared/ui/AppButton.vue'
import AppDatePicker, { type AppDateValue } from '@/shared/ui/AppDatePicker.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'

const page = ref(1)
const pageSize = ref(20)
const dateRange = ref<AppDateValue>(null)
const actorUserId = ref('')
const action = ref<AuditAction | null>(null)
const appliedFilters = ref<{
  dateRange: [number, number] | null
  actorUserId: string
  action: AuditAction | null
}>({
  dateRange: null,
  actorUserId: '',
  action: null,
})

const auditActions: AuditAction[] = [
  'access_management.create_member',
  'access_management.update_member',
  'access_management.reset_member_password',
  'access_management.create_membership',
  'access_management.update_membership',
  'access_management.create_team',
  'access_management.update_team',
]
const actionOptions: SelectOption[] = auditActions.map((value) => ({
  value,
  label: getAuditActionLabel(value),
}))

const params = computed(() => {
  const range = appliedFilters.value.dateRange
  return {
    page: page.value,
    pageSize: pageSize.value,
    createdFrom: range
      ? dayjs(range[0]).startOf('day').toISOString()
      : undefined,
    createdTo: range
      ? dayjs(range[1]).add(1, 'day').startOf('day').toISOString()
      : undefined,
    actorUserId: appliedFilters.value.actorUserId || undefined,
    action: appliedFilters.value.action ?? undefined,
  }
})
const auditLogsQuery = useAuditLogsQuery(params)

const rows = computed(() => auditLogsQuery.data.value?.items ?? [])
const total = computed(() => auditLogsQuery.data.value?.total ?? 0)
const error = computed(() =>
  auditLogsQuery.isError.value
    ? getErrorMessage(auditLogsQuery.error.value)
    : null,
)

const columns: DataTableColumns<AuditLogViewModel> = [
  {
    title: '时间',
    key: 'createdAt',
    width: 180,
    render: (log) => dayjs(log.createdAt).format('YYYY-MM-DD HH:mm:ss'),
  },
  {
    title: '操作人',
    key: 'actorDisplayName',
    minWidth: 140,
    ellipsis: { tooltip: true },
  },
  {
    title: '操作',
    key: 'action',
    minWidth: 150,
    render: (log) => getAuditActionLabel(log.action),
  },
  {
    title: '目标',
    key: 'target',
    minWidth: 180,
    render: (log) => getAuditTargetLabel(log),
  },
  {
    title: '结果 / 摘要',
    key: 'summary',
    minWidth: 240,
    ellipsis: { tooltip: true },
    render: (log) => h('span', getAuditSummary(log)),
  },
]

function setPageSize(value: number): void {
  pageSize.value = value
  page.value = 1
}

function query(): void {
  appliedFilters.value = {
    dateRange: Array.isArray(dateRange.value) ? dateRange.value : null,
    actorUserId: actorUserId.value.trim(),
    action: action.value,
  }
  page.value = 1
}

function reset(): void {
  dateRange.value = null
  actorUserId.value = ''
  action.value = null
  appliedFilters.value = {
    dateRange: null,
    actorUserId: '',
    action: null,
  }
  page.value = 1
}
</script>

<template>
  <SettingsLayout>
    <div class="audit-log-page">
      <TableToolbar class="audit-log-page__toolbar">
        <h1 class="audit-log-page__title">操作日志</h1>
        <template #actions>
          <AppDatePicker
            v-model="dateRange"
            type="daterange"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
          />
          <AppInput
            v-model="actorUserId"
            aria-label="操作人 ID"
            width="md"
            clearable
            placeholder="操作人 ID"
            @keyup.enter="query"
          />
          <AppSelect
            v-model="action"
            width="md"
            clearable
            :options="actionOptions"
            placeholder="全部操作"
          />
          <AppButton tone="text" @click="reset">重置</AppButton>
          <AppButton tone="primary" @click="query">查询</AppButton>
        </template>
      </TableToolbar>
      <div class="audit-log-page__table">
      <DataTable
        :columns="columns"
        :data="rows"
        :loading="auditLogsQuery.isPending.value"
        :error="error"
        viewport="fill"
        appearance="list"
        empty-description="暂无操作日志"
        @retry="auditLogsQuery.refetch()"
      />
      <PaginationBar
        v-model:page="page"
        :page-size="pageSize"
        :item-count="total"
        @update:page-size="setPageSize"
      />
      </div>
    </div>
  </SettingsLayout>
</template>

<style scoped>
.audit-log-page {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  gap: var(--space-3);
}

.audit-log-page__toolbar {
  flex-wrap: nowrap;
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
}

.audit-log-page__toolbar :deep(.table-toolbar__actions) {
  margin-left: auto;
  flex-wrap: nowrap;
}

@media (max-width: 1200px) {
  .audit-log-page__toolbar {
    flex-wrap: wrap;
  }

  .audit-log-page__toolbar :deep(.table-toolbar__actions) {
    flex: 1 1 100%;
    margin-left: 0;
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}

.audit-log-page__title {
  margin: 0;
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
}

.audit-log-page__table {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: var(--space-3);
}
</style>
