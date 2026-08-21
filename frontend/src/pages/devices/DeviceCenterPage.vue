<script setup lang="ts">
import {
  DeviceDetailDrawer,
  DeviceFilterBar,
  DeviceFormDialog,
  DeviceListTable,
  YingdaoApplicationsDrawer,
  useDeviceManagement,
} from '@/features/device-management'
import ManagementListSection from '@/shared/components/ManagementListSection.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'
import AppButton from '@/shared/ui/AppButton.vue'

const management = useDeviceManagement()
</script>

<template>
  <div class="page-container device-center-page">
    <DeviceFilterBar
      v-model="management.filterDraft.value"
      :statistics="management.statistics.value"
      :refreshing="management.refreshing.value"
      @refresh="management.refreshList"
    >
      <template #primary-action>
        <AppButton tone="primary" @click="management.openCreate">
          + 添加设备
        </AppButton>
      </template>
    </DeviceFilterBar>

    <ManagementListSection class="device-list-section">
      <DeviceListTable
        v-model:checked-row-keys="management.selectedDeviceIds.value"
        :rows="management.visibleRows.value"
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
    </ManagementListSection>

    <DeviceDetailDrawer
      v-model:show="management.detailVisible.value"
      :device="management.detailDevice.value"
      :loading="management.detailLoading.value"
      :error="management.detailError.value"
      :yingdao-inventory="management.yingdaoInventory.value"
      :provider-inventory-loading="management.providerInventoryLoading.value"
      :provider-inventory-error="management.providerInventoryError.value"
      :yingdao-refreshing="management.yingdaoRefreshing.value"
      :current-execution="management.detailCurrentExecution.value"
      :bound-shop-count="management.detailBoundShopCount.value"
      :recent-executions="management.recentExecutions.value"
      @retry="management.retryDetail"
      @retry-provider-inventory="management.retryProviderInventory"
      @refresh-yingdao="management.refreshYingdao"
      @view-yingdao-applications="management.openYingdaoApplications"
    />

    <YingdaoApplicationsDrawer
      v-model:show="management.applicationsVisible.value"
      :applications="management.yingdaoInventory.value?.applications ?? []"
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
.device-center-page {
  height: 100%;
  min-height: 0;
}
</style>
