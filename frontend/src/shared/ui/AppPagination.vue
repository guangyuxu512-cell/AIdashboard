<script setup lang="ts">
import { NPagination } from 'naive-ui'

withDefaults(
  defineProps<{
    page: number
    pageSize: number
    itemCount: number
    pageSizes?: number[]
    showSizePicker?: boolean
    disabled?: boolean
  }>(),
  {
    pageSizes: () => [10, 20, 50, 100],
    showSizePicker: true,
    disabled: false,
  },
)

defineEmits<{
  'update:page': [value: number]
  'update:pageSize': [value: number]
}>()
</script>

<template>
  <NPagination
    size="medium"
    :page="page"
    :page-size="pageSize"
    :item-count="itemCount"
    :page-sizes="pageSizes"
    :show-size-picker="showSizePicker"
    :disabled="disabled"
    @update:page="$emit('update:page', $event)"
    @update:page-size="$emit('update:pageSize', $event)"
  />
</template>
