<script setup lang="ts">
import { MobileListContextCard, MobileSearchField } from '@/shared/ui'

import type { TaskStatusFilter } from '../model/task-filter'
import TaskMetrics from './TaskMetrics.vue'

defineProps<{
  searchQuery: string
  filter: TaskStatusFilter
  totals: {
    running: number | null
    pending: number | null
    exception: number | null
    completed: number | null
  }
  metricsBusy: boolean
  resultLabel: string
  resultCount: string
  dateLabel: string
}>()

const emit = defineEmits<{
  updateSearchQuery: [value: string]
  selectFilter: [filter: Exclude<TaskStatusFilter, 'all'>]
}>()
</script>

<template>
  <section
    class="task-list-controls"
    aria-label="任务列表工具"
    data-testid="task-list-controls"
  >
    <MobileSearchField
      :model-value="searchQuery"
      placeholder="搜索任务"
      aria-label="搜索任务"
      data-testid="task-search"
      @update:model-value="emit('updateSearchQuery', $event)"
    />

    <TaskMetrics
      :filter="filter"
      :totals="totals"
      :busy="metricsBusy"
      @select="emit('selectFilter', $event)"
    />

    <MobileListContextCard
      :label="resultLabel"
      :count="resultCount"
      :context-label="dateLabel"
      aria-label="当前任务查询结果"
    />
  </section>
</template>

<style scoped>
.task-list-controls {
  display: grid;
  width: 100%;
  min-width: 0;
  flex: none;
  gap: var(--task-list-fixed-controls-gap);
  padding: 0 max(var(--task-list-page-padding-x), var(--safe-area-right)) 0
    max(var(--task-list-page-padding-x), var(--safe-area-left));
}
</style>
