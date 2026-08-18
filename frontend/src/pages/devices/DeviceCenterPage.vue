<script setup lang="ts">
import {
  DeviceDetailDrawer,
  DeviceFilterBar,
  DeviceFormDialog,
  DeviceListTable,
  useDeviceManagement,
} from '@/features/device-management'
import PageSection from '@/shared/components/PageSection.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'
import AppButton from '@/shared/ui/AppButton.vue'

const management = useDeviceManagement()
</script>

<template>
  <div class="page-container device-center-page">
    <DeviceFilterBar
      v-model="management.filterDraft.value"
      :available="management.filtersAvailable"
      @query="management.query"
      @reset="management.resetFilters"
    >
      <template #primary-action>
        <AppButton tone="primary" @click="management.openCreate">
          + 添加设备
        </AppButton>
      </template>
    </DeviceFilterBar>

    <PageSection>
      <div class="device-list-pattern">
        <DeviceListTable
          :rows="management.rows.value"
          :loading="management.listLoading.value"
          :error="management.listError.value"
          @view="management.openDetail"
          @edit="management.openEdit"
          @retry="management.retryList"
        />
        <PaginationBar
          v-model:page="management.page.value"
          :page-size="management.pageSize.value"
          :item-count="management.total.value"
          @update:page-size="management.setPageSize"
        />
      </div>
    </PageSection>

    <DeviceDetailDrawer
      v-model:show="management.detailVisible.value"
      :device="management.detailDevice.value"
      :loading="management.detailLoading.value"
      :error="management.detailError.value"
      @retry="management.retryDetail"
    />

    <DeviceFormDialog
      v-model:show="management.formVisible.value"
      :mode="management.formMode.value"
      :initial-value="management.formInitialValue.value"
      :submitting="management.formSubmitting.value"
      @save="management.saveDevice"
    />
  </div>
</template>

<style scoped>
.device-list-pattern {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-4);
}
</style>
