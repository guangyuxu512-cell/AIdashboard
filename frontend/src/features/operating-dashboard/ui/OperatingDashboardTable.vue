<script setup lang="ts">
import { computed, h } from 'vue'
import type { DataTableColumns } from 'naive-ui'

import { PlatformDisplay } from '@/entities/platform'
import DataTable from '@/shared/components/DataTable.vue'

import {
  formatDashboardCollectedAt,
  formatDashboardCount,
  formatDashboardCurrency,
  formatMerchantExperience,
} from '../model/formatters'
import type { OperatingDashboardTableRow } from '../model/types'

defineProps<{
  rows: OperatingDashboardTableRow[]
  loading?: boolean
  error?: string | null
}>()

defineEmits<{ retry: [] }>()

const columns = computed<DataTableColumns<OperatingDashboardTableRow>>(() => [
  {
    title: '店铺',
    key: 'shopName',
    width: 190,
    fixed: 'left',
    ellipsis: { tooltip: true },
  },
  {
    title: '平台',
    key: 'platform',
    width: 110,
    align: 'center',
    render: (row) => h(PlatformDisplay, { code: row.platform }),
  },
  {
    title: '成交金额',
    key: 'turnoverCents',
    width: 132,
    align: 'center',
    render: (row) => formatDashboardCurrency(row.turnoverCents),
  },
  {
    title: '成交订单',
    key: 'orderCount',
    width: 112,
    align: 'center',
    render: (row) => formatDashboardCount(row.orderCount),
  },
  {
    title: '退货数量',
    key: 'returnQuantity',
    width: 112,
    align: 'center',
    render: (row) => formatDashboardCount(row.returnQuantity),
  },
  {
    title: '商家体验分',
    key: 'experience',
    width: 270,
    align: 'center' as const,
    ellipsis: { tooltip: true },
    render: (row: OperatingDashboardTableRow) => {
      const value = formatMerchantExperience(row.experience)
      return h(
        'span',
        { class: 'operating-dashboard-table__experience', title: value },
        value,
      )
    },
  },
  {
    title: '更新时间',
    key: 'collectedAt',
    width: 136,
    align: 'center',
    render: (row) => formatDashboardCollectedAt(row.collectedAt),
  },
])
</script>

<template>
  <DataTable
    :columns="columns"
    :data="rows"
    :loading="loading"
    :error="error"
    :row-key="(row: OperatingDashboardTableRow) => row.shopId"
    :scroll-x="1062"
    appearance="list"
    viewport="fill"
    class="operating-dashboard-table"
    empty-description="当前筛选范围暂无经营数据"
    @retry="$emit('retry')"
  />
</template>

<style scoped>
.operating-dashboard-table {
  min-height: 0;
  flex: 1;
}

.operating-dashboard-table :deep(.n-data-table-tbody .n-data-table-td) {
  height: var(--table-list-row-slot-height);
  vertical-align: middle;
}

.operating-dashboard-table :deep(.operating-dashboard-table__experience) {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: middle;
  white-space: nowrap;
}
</style>
