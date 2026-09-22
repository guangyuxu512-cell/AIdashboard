<script setup lang="ts">
import { computed, h } from 'vue'
import type {
  DataTableColumns,
  DataTableProps,
  DataTableSortOrder,
  DataTableSortState,
} from 'naive-ui'

import { PlatformDisplay } from '@/entities/platform'
import EmptyState from '@/shared/components/EmptyState.vue'
import AppTable from '@/shared/ui/AppTable.vue'

import {
  formatDashboardCollectedAt,
  formatDashboardCount,
  formatDashboardCurrency,
  formatMerchantExperience,
} from '../model/formatters'
import type {
  OperatingDashboardSort,
  OperatingDashboardSortField,
  OperatingDashboardTableRow,
} from '../model/types'

type DashboardTableThemeOverrides = NonNullable<
  DataTableProps['themeOverrides']
>

const props = withDefaults(defineProps<{
  rows: OperatingDashboardTableRow[]
  loading?: boolean
  emptyDescription?: string
  sort?: OperatingDashboardSort | null
  sortingEnabled?: boolean
}>(), {
  sort: null,
  sortingEnabled: false,
})

const emit = defineEmits<{
  'update:sort': [value: OperatingDashboardSort | null]
}>()

const SORTABLE_FIELDS = new Set<OperatingDashboardSortField>([
  'shopName',
  'turnoverCents',
  'orderCount',
  'returnQuantity',
  'collectedAt',
])

/**
 * Naive gives an active sort column a hover-toned background by default.
 * The dashboard keeps sort state in the existing header text and arrow only;
 * these values deliberately reuse the table's established surface tokens.
 */
const DASHBOARD_SORT_THEME_OVERRIDES: DashboardTableThemeOverrides = {
  thColorSorting: 'var(--bg-subtle)',
  tdColorSorting: 'var(--bg-surface-solid)',
}

function getSortOrder(field: OperatingDashboardSortField): DataTableSortOrder {
  if (!props.sortingEnabled || props.sort?.field !== field) return false
  return props.sort.direction === 'asc' ? 'ascend' : 'descend'
}

function nextNameSortOrder(order: DataTableSortOrder): DataTableSortOrder {
  if (order === false) return 'ascend'
  return order === 'ascend' ? 'descend' : false
}

function nextMetricSortOrder(order: DataTableSortOrder): DataTableSortOrder {
  if (order === false) return 'descend'
  return order === 'descend' ? 'ascend' : false
}

function sortableColumn(
  field: OperatingDashboardSortField,
  customNextSortOrder: (order: DataTableSortOrder) => DataTableSortOrder,
) {
  if (!props.sortingEnabled) return {}
  return {
    sorter: true,
    sortOrder: getSortOrder(field),
    customNextSortOrder,
  }
}

function handleSorterUpdate(
  value: DataTableSortState | DataTableSortState[] | null,
): void {
  const sorter = Array.isArray(value) ? value[0] ?? null : value
  if (
    !sorter ||
    sorter.order === false ||
    typeof sorter.columnKey !== 'string' ||
    !SORTABLE_FIELDS.has(sorter.columnKey as OperatingDashboardSortField)
  ) {
    emit('update:sort', null)
    return
  }
  const field = sorter.columnKey as OperatingDashboardSortField
  // Naive DataTable starts every newly selected column at descend before it
  // consults customNextSortOrder. The dashboard's name column intentionally
  // starts at ascend; later clicks still use the native cycle and icon.
  const direction =
    field === 'shopName' && props.sort?.field !== field
      ? 'asc'
      : sorter.order === 'ascend'
        ? 'asc'
        : 'desc'
  emit('update:sort', {
    field,
    direction,
  })
}

const columns = computed<DataTableColumns<OperatingDashboardTableRow>>(() => [
  {
    title: '店铺',
    key: 'shopName',
    width: 190,
    fixed: 'left',
    ellipsis: { tooltip: true },
    ...sortableColumn('shopName', nextNameSortOrder),
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
    ...sortableColumn('turnoverCents', nextMetricSortOrder),
  },
  {
    title: '成交订单',
    key: 'orderCount',
    width: 112,
    align: 'center',
    render: (row) => formatDashboardCount(row.orderCount),
    ...sortableColumn('orderCount', nextMetricSortOrder),
  },
  {
    title: '退货数量',
    key: 'returnQuantity',
    width: 112,
    align: 'center',
    render: (row) => formatDashboardCount(row.returnQuantity),
    ...sortableColumn('returnQuantity', nextMetricSortOrder),
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
    ...sortableColumn('collectedAt', nextMetricSortOrder),
  },
])
</script>

<template>
  <div class="operating-dashboard-table">
    <AppTable
      :columns="columns"
      :data="rows"
      :loading="loading"
      :row-key="(row: OperatingDashboardTableRow) => row.shopId"
      :scroll-x="1062"
      :theme-overrides="
        sortingEnabled ? DASHBOARD_SORT_THEME_OVERRIDES : undefined
      "
      appearance="list"
      fill
      @update:sorter="handleSorterUpdate"
    >
      <template #empty>
        <EmptyState
          :description="emptyDescription ?? '当前筛选范围暂无经营数据'"
        />
      </template>
    </AppTable>
  </div>
</template>

<style scoped>
.operating-dashboard-table {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}

.operating-dashboard-table :deep(.n-data-table-tbody .n-data-table-td) {
  height: var(--table-list-row-slot-height);
  vertical-align: middle;
}

/* Naive applies its sorting class after hover. Restore the normal row-hover
 * token only when the pointer is over an active sort cell. */
.operating-dashboard-table
  :deep(.n-data-table-td--sorting.n-data-table-td--hover) {
  background-color: var(--n-merged-td-color-hover);
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
