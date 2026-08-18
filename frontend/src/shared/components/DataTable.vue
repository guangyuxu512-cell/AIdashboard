<script setup lang="ts">
import type { DataTableProps, DataTableRowKey } from 'naive-ui'

import AppTable from '@/shared/ui/AppTable.vue'

import EmptyState from './EmptyState.vue'
import ErrorState from './ErrorState.vue'
import LoadingState from './LoadingState.vue'

const props = withDefaults(
  defineProps<{
    columns: DataTableProps['columns']
    data?: DataTableProps['data']
    loading?: boolean
    error?: string | null
    rowKey?: DataTableProps['rowKey']
    scrollX?: number
    emptyDescription?: string
    checkedRowKeys?: DataTableRowKey[]
    viewport?: 'auto' | 'stable'
    appearance?: 'grid' | 'list'
  }>(),
  {
    data: () => [],
    loading: false,
    error: null,
    rowKey: undefined,
    scrollX: undefined,
    emptyDescription: '暂无数据',
    checkedRowKeys: () => [],
    viewport: 'auto',
    appearance: 'grid',
  },
)

defineEmits<{
  retry: []
  'update:checkedRowKeys': [keys: DataTableRowKey[]]
}>()
</script>

<template>
  <div
    class="data-table"
    :class="[
      `data-table--${viewport}`,
      `data-table--appearance-${appearance}`,
    ]"
  >
    <LoadingState v-if="loading && (props.data?.length ?? 0) === 0" />
    <ErrorState
      v-else-if="error"
      :description="error"
      retryable
      @retry="$emit('retry')"
    />
    <EmptyState
      v-else-if="!loading && (props.data?.length ?? 0) === 0"
      :description="emptyDescription"
    />
    <AppTable
      v-else
      :columns="columns"
      :data="data"
      :loading="loading"
      :row-key="rowKey"
      :scroll-x="scrollX"
      :checked-row-keys="checkedRowKeys"
      :appearance="appearance"
      @update:checked-row-keys="$emit('update:checkedRowKeys', $event)"
    />
  </div>
</template>

<style scoped>
.data-table {
  min-width: 0;
}

.data-table--stable {
  min-height: var(--table-list-viewport-height);
}

.data-table--stable > :deep(.state-panel) {
  min-height: var(--table-list-viewport-height);
}
</style>
