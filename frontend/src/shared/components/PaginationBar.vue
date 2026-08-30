<script setup lang="ts">
import AppPagination from '@/shared/ui/AppPagination.vue'
import { STANDARD_PAGE_SIZE_OPTIONS } from '@/shared/ui/pagination'

withDefaults(
  defineProps<{
    page: number
    pageSize: number
    itemCount: number
    pageSizes?: number[]
  }>(),
  {
    pageSizes: () => [...STANDARD_PAGE_SIZE_OPTIONS],
  },
)

defineEmits<{
  'update:page': [value: number]
  'update:pageSize': [value: number]
}>()
</script>

<template>
  <div class="pagination-bar">
    <span>共 {{ itemCount }} 条</span>
    <AppPagination
      :page="page"
      :page-size="pageSize"
      :item-count="itemCount"
      :page-sizes="pageSizes"
      @update:page="$emit('update:page', $event)"
      @update:page-size="$emit('update:pageSize', $event)"
    />
  </div>
</template>

<style scoped>
.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}
</style>
