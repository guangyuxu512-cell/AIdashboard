<script setup lang="ts">
import { NDataTable } from 'naive-ui'
import type { DataTableProps } from 'naive-ui'

withDefaults(
  defineProps<{
    columns: DataTableProps['columns']
    data?: DataTableProps['data']
    loading?: boolean
    bordered?: boolean
    striped?: boolean
    rowKey?: DataTableProps['rowKey']
    scrollX?: number
  }>(),
  {
    data: () => [],
    loading: false,
    bordered: false,
    striped: false,
    rowKey: undefined,
    scrollX: undefined,
  },
)
</script>

<template>
  <NDataTable
    size="medium"
    :columns="columns"
    :data="data"
    :loading="loading"
    :bordered="bordered"
    :striped="striped"
    :row-key="rowKey"
    :scroll-x="scrollX"
    :single-line="false"
  />
</template>
