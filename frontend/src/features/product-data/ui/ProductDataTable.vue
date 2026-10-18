<script setup lang="ts">
import { computed, h } from 'vue'
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
import { productMetricTooltip } from '../model/metrics'
import { PRODUCT_METRIC_TOOLTIP_STYLE } from './metric-tooltip'
import {
  PRODUCT_DISPLAY_COLUMNS,
  type ProductDisplayColumnId,
  type ProductColumnId,
  type ProductDataQuery,
  type ProductDataRow,
} from '../model/types'
import {
  productDisplayColumn,
  productDisplayMetricId,
  sanitizeProductDisplayColumns,
} from '../model/display-fields'

const props = defineProps<{
  rows: ProductDataRow[]
  visibleColumns: ProductDisplayColumnId[]
  checked: DataTableRowKey[]
  sort: ProductDataQuery['sort']
  loading: boolean
  error: string | null
  enabled: boolean
  nativeOnly?: boolean
}>()
const emit = defineEmits<{
  'update:checked': [keys: DataTableRowKey[]]
  'update:sort': [sort: ProductDataQuery['sort']]
  detail: [row: ProductDataRow]
  retry: []
}>()
// Own column budget: 48px image + 8px gap + ID/copy slots, not selection's layout.
const productColumnWidth = 304
const displayedColumns = computed(() =>
  sanitizeProductDisplayColumns(props.visibleColumns),
)
const widths = computed(
  () =>
    44 +
    productColumnWidth +
    88 +
    displayedColumns.value.reduce(
      (sum, id) => sum + (productDisplayColumn(id)?.width ?? 0),
      0,
    ),
)
function value(row: ProductDataRow, id: ProductDisplayColumnId) {
  if (id === 'shop') return row.shopName
  const metricId = productDisplayMetricId(id)
  if (!metricId) return '—'
  const metric = row.metrics[metricId],
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
    width: productColumnWidth,
    minWidth: productColumnWidth,
    maxWidth: productColumnWidth,
    fixed: 'left',
    render: (row) =>
      h(ProductInfoCell, {
        productId: row.productId,
        title: row.title,
        imageUrl: row.imageUrl,
        density: 'compact',
      }),
  },
  ...displayedColumns.value.map((id) => {
    const definition = productDisplayColumn(id)!,
      metricId = productDisplayMetricId(id),
      width = definition.width
    return {
      title: metricId
        ? () =>
            h(
              NTooltip,
              { contentStyle: PRODUCT_METRIC_TOOLTIP_STYLE },
              {
                trigger: () => h('span', definition.label),
                default: () => productMetricTooltip(metricId),
              },
            )
        : definition.label,
      key: id,
      width,
      minWidth: width,
      maxWidth: width,
      align: 'center' as const,
      sorter:
        props.enabled &&
        (!props.nativeOnly || id === 'shop' || metricId !== null),
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
    !PRODUCT_DISPLAY_COLUMNS.some((column) => column.id === field)
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
    show-header-when-empty
    :theme-overrides="{ tdPaddingMedium: 'var(--space-2) var(--space-3)' }"
    empty-description="所选范围暂无商品数据"
    @update:checked-row-keys="$emit('update:checked', $event)"
    @update:sorter="sortChanged"
    @retry="$emit('retry')"
  />
</template>
