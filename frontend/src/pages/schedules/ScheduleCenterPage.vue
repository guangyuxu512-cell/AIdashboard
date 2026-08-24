<script setup lang="ts">
import {
  ScheduleDetailDrawer,
  ScheduleFilterBar,
  ScheduleFormDialog,
  ScheduleListTable,
  ScheduleRemoveDialog,
  useScheduleManagement,
} from '@/features/schedule-management'
import { TaskRuntimeDrawer } from '@/features/task-runtime'
import ManagementListSection from '@/shared/components/ManagementListSection.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'

const management = useScheduleManagement()
</script>

<template>
  <div class="page-container schedule-center-page">
    <ScheduleFilterBar
      v-model="management.filterDraft.value"
      :device-options="management.deviceOptions.value"
      :device-options-loading="management.deviceOptionsLoading.value"
      @query="management.query"
      @reset="management.resetFilters"
      @create="management.openCreate"
    />

    <ManagementListSection>
      <ScheduleListTable
        :rows="management.rows.value"
        :loading="management.listLoading.value"
        :error="management.listError.value"
        @detail="management.openDetail"
        @toggle="management.toggleEnabled"
        @retry="management.retryList"
      />
      <PaginationBar
        v-model:page="management.page.value"
        :page-size="management.pageSize.value"
        :item-count="management.total.value"
        @update:page-size="management.setPageSize"
      />
    </ManagementListSection>

    <ScheduleDetailDrawer
      v-model:show="management.detailVisible.value"
      :schedule="management.detail.value"
      :loading="management.detailLoading.value"
      :error="management.detailError.value"
      :status-changing="management.submitting.value"
      :removing="management.removing.value"
      @retry="management.retryDetail"
      @edit="management.editSelected"
      @toggle="
        management.detail.value &&
        management.toggleEnabled(management.detail.value)
      "
      @remove="
        management.detail.value &&
        management.confirmRemove(management.detail.value)
      "
      @runtime="management.openRuntime"
    />

    <ScheduleFormDialog
      v-model:show="management.formVisible.value"
      :mode="management.formMode.value"
      :schedule="management.detail.value"
      :device-options="management.deviceOptions.value"
      :device-options-loading="management.deviceOptionsLoading.value"
      :submitting="management.submitting.value"
      @submit="management.save"
    />

    <ScheduleRemoveDialog
      v-model:show="management.removeVisible.value"
      :schedule="management.detail.value"
      :submitting="management.removing.value"
      @confirm="management.remove"
    />

    <TaskRuntimeDrawer
      v-model:show="management.runtimeVisible.value"
      :task-id="management.runtimeTaskId.value"
      :device-name="management.runtimeDeviceName.value"
    />
  </div>
</template>

<style scoped>
.schedule-center-page {
  height: 100%;
  min-height: 0;
}
</style>
