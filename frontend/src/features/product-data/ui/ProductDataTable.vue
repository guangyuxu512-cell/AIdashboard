<script setup lang="ts">
import { computed, h } from 'vue'
import dayjs from 'dayjs'
import {
  NTooltip,
  type DataTableColumns,
  type DataTableRowKey,
  type DataTableSortState,
} from 'naive-ui'
import { ProductInfoCell } from '@/entities/product'
import { DataTable } from '@/shared/components'
import { AppButton } from '@/shared/ui'
import {
  formatProductMetric,
  PRODUCT_METRIC_STATE_LABELS,
} from '../model/query'
import {
  PRODUCT_COLUMNS,
  type ProductColumnId,
  type ProductDataQuery,
  type ProductDataRow,
} from '../model/types'

const props = defineProps<{
  rows: ProductDataRow[]
  visibleColumns: ProductColumnId[]
  checked: DataTableRowKey[]
  sort: ProductDataQuery['sort']
  loading: boolean
  error: string | null
  enabled: boolean
}>()
const emit = defineEmits<{
  'update:checked': [keys: DataTableRowKey[]]
  'update:sort': [sort: ProductDataQuery['sort']]
  detail: [row: ProductDataRow]
  retry: []
}>()
const widths = computed(
  () =>
    44 +
    360 +
    88 +
    props.visibleColumns.reduce(
      (sum, id) =>
        sum + (PRODUCT_COLUMNS.find((column) => column.id === id)?.width ?? 0),
      0,
    ),
)
function value(row: ProductDataRow, id: ProductColumnId) {
  if (id === 'shop') return row.shopName
  if (id === 'group') return row.groupName ?? '未分组'
  if (id === 'selling') return row.selling === 'on-sale' ? '在售' : '停售'
  if (id === 'carrier')
    return { card: '商品卡', video: '短视频', live: '直播' }[row.carrier]
  if (id === 'updatedAt')
    return dayjs(row.retrievedAt).format('YYYY-MM-DD HH:mm')
  const metric = row.metrics[id],
    text = formatProductMetric(metric)
  return metric.state === 'available'
    ? text
    : h(NTooltip, null, {
        trigger: () =>
          h(
            'span',
            {
              tabindex: 0,
              'aria-label': PRODUCT_METRIC_STATE_LABELS[metric.state],
            },
            text,
          ),
        default: () => PRODUCT_METRIC_STATE_LABELS[metric.state],
      })
}
const columns = computed<DataTableColumns<ProductDataRow>>(() => [
  {
    type: 'selection',
    width: 44,
    fixed: 'left',
    disabled: () => !props.enabled,
  },
  {
    title: '商品信息',
    key: 'product',
    width: 360,
    fixed: 'left',
    render: (row) =>
      h(ProductInfoCell, {
        productId: row.productId,
        title: row.title,
        imageUrl: row.imageUrl,
      }),
  },
  ...props.visibleColumns.map((id) => {
    const definition = PRODUCT_COLUMNS.find((column) => column.id === id)!
    return {
      title: definition.label,
      key: id,
      width: definition.width,
      align: 'center' as const,
      sorter: props.enabled,
      sortOrder:
        props.sort?.field === id
          ? props.sort.direction === 'asc'
            ? ('ascend' as const)
            : ('descend' as const)
          : (false as const),
      customNextSortOrder: (order: 'ascend' | 'descend' | false) =>
        order === false
          ? ('descend' as const)
          : order === 'descend'
            ? ('ascend' as const)
            : (false as const),
      ellipsis: { tooltip: true },
      render: (row: ProductDataRow) => value(row, id),
    }
  }),
  {
    title: '操作',
    key: 'actions',
    width: 88,
    fixed: 'right',
    align: 'center',
    render: (row) =>
      h(
        AppButton,
        { tone: 'text', onClick: () => emit('detail', row) },
        { default: () => '详情' },
      ),
  },
])
function sortChanged(value: DataTableSortState | DataTableSortState[] | null) {
  const sorter = Array.isArray(value) ? value[0] : value
  const field = sorter?.columnKey
  if (
    !sorter ||
    !sorter.order ||
    !PRODUCT_COLUMNS.some((column) => column.id === field)
  )
    emit('update:sort', null)
  else
    emit('update:sort', {
      field: field as ProductColumnId,
      direction: sorter.order === 'ascend' ? 'asc' : 'desc',
    })
}
</script>

<template>
  <DataTable
    class="product-data-table"
    :columns="columns"
    :data="rows"
    :loading="loading"
    :error="error"
    :row-key="(row) => row.id"
    :scroll-x="widths"
    :checked-row-keys="checked"
    viewport="fill"
    appearance="list"
    :theme-overrides="{ tdPaddingMedium: 'var(--space-2) var(--space-3)' }"
    empty-description="所选范围暂无商品数据"
    @update:checked-row-keys="$emit('update:checked', $event)"
    @update:sorter="sortChanged"
    @retry="$emit('retry')"
  />
</template>
