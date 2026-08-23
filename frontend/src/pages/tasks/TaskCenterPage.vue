<script setup lang="ts">
import {
  TaskFilterBar,
  TaskListTable,
  useTaskManagement,
} from '@/features/task-management'
import { TaskRuntimeDrawer } from '@/features/task-runtime'
import ManagementListSection from '@/shared/components/ManagementListSection.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'

const management = useTaskManagement()
</script>

<template>
  <div class="page-container task-center-page">
    <TaskFilterBar
      v-model="management.filterDraft.value"
      :device-options="management.deviceOptions.value"
      :device-options-loading="management.deviceOptionsLoading.value"
      @query="management.query"
      @reset="management.resetFilters"
    />

    <ManagementListSection class="task-list-section">
      <TaskListTable
        :rows="management.rows.value"
        :loading="management.listLoading.value"
        :error="management.listError.value"
        @detail="management.openRuntime"
        @retry="management.retryList"
      />
      <PaginationBar
        v-model:page="management.page.value"
        :page-size="management.pageSize.value"
        :item-count="management.total.value"
        @update:page-size="management.setPageSize"
      />
    </ManagementListSection>

    <TaskRuntimeDrawer
      v-model:show="management.runtimeVisible.value"
      :task-id="management.runtimeTaskId.value"
      :device-name="management.runtimeDeviceName.value"
    />
  </div>
</template>

<style scoped>
.task-center-page {
  height: 100%;
  min-height: 0;
}
</style>
