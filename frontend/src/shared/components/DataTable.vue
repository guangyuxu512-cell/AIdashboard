<script setup lang="ts">
import type { DataTableProps } from 'naive-ui'

import AppTable from '@/shared/ui/AppTable.vue'

import EmptyState from './EmptyState.vue'
import ErrorState from './ErrorState.vue'

const props = withDefaults(
  defineProps<{
    columns: DataTableProps['columns']
    data?: DataTableProps['data']
    loading?: boolean
    error?: string | null
    rowKey?: DataTableProps['rowKey']
    scrollX?: number
    emptyDescription?: string
  }>(),
  {
    data: () => [],
    loading: false,
    error: null,
    rowKey: undefined,
    scrollX: undefined,
    emptyDescription: '暂无数据',
  },
)

defineEmits<{ retry: [] }>()
</script>

<template>
  <ErrorState v-if="error" :description="error" retryable @retry="$emit('retry')" />
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
  />
</template>
