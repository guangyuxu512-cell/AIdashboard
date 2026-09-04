<script setup lang="ts">
import { computed, h, ref } from 'vue'
import type { DataTableColumns } from 'naive-ui'
import dayjs from 'dayjs'

import {
  getAuditActionLabel,
  getAuditSummary,
  getAuditTargetLabel,
  type AuditLogViewModel,
  useAuditLogsQuery,
} from '@/entities/audit-log'
import SystemSettingsNavigation from '@/features/system-settings/ui/SystemSettingsNavigation.vue'
import DataTable from '@/shared/components/DataTable.vue'
import ManagementListSection from '@/shared/components/ManagementListSection.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'
import { getErrorMessage } from '@/shared/api'

const page = ref(1)
const pageSize = ref(20)
const params = computed(() => ({ page: page.value, pageSize: pageSize.value }))
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
</script>

<template>
  <div class="page-container audit-log-page">
    <SystemSettingsNavigation />
    <ManagementListSection>
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
    </ManagementListSection>
  </div>
</template>

<style scoped>
.audit-log-page {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  gap: var(--space-4);
}
</style>
