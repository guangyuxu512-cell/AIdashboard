<script setup lang="ts">
import { NDataTable } from 'naive-ui'
import type {
  DataTableProps,
  DataTableRowData,
  DataTableRowKey,
} from 'naive-ui'

const props = withDefaults(
  defineProps<{
    columns: DataTableProps['columns']
    data?: DataTableProps['data']
    loading?: boolean
    bordered?: boolean
    striped?: boolean
    rowKey?: DataTableProps['rowKey']
    scrollX?: number
    checkedRowKeys?: DataTableRowKey[]
    appearance?: 'grid' | 'list'
  }>(),
  {
    data: () => [],
    loading: false,
    bordered: false,
    striped: false,
    rowKey: undefined,
    scrollX: undefined,
    checkedRowKeys: () => [],
    appearance: 'grid',
  },
)

defineEmits<{
  'update:checkedRowKeys': [keys: DataTableRowKey[]]
}>()

function rowClassName(row: DataTableRowData): string {
  if (!props.rowKey) return ''
  const key = props.rowKey(row)
  return props.checkedRowKeys.includes(key) ? 'app-table__row--selected' : ''
}
</script>

<template>
  <NDataTable
    class="app-table"
    :class="`app-table--${appearance}`"
    size="medium"
    :columns="columns"
    :data="data"
    :loading="loading"
    :bordered="bordered"
    :striped="striped"
    :row-key="rowKey"
    :scroll-x="scrollX"
    :checked-row-keys="props.checkedRowKeys"
    :row-class-name="rowClassName"
    :single-line="appearance === 'list'"
    @update:checked-row-keys="$emit('update:checkedRowKeys', $event)"
  />
</template>

<style scoped>
.app-table--list :deep(.n-data-table-th),
.app-table--list :deep(.n-data-table-td) {
  text-align: center;
}

.app-table--list
  :deep(.n-data-table-tr.app-table__row--selected .n-data-table-td) {
  background-color: var(--color-primary-soft);
}
</style>
