<script setup lang="ts">
import { computed, defineAsyncComponent, ref } from 'vue'
import { storeToRefs } from 'pinia'

import {
  createOfficeStations,
  DeviceOfficeToolbar,
  useDeviceOfficeView,
  type OfficeStationViewModel,
} from '@/features/device-office'
import {
  DeviceDetailDrawer,
  DeviceFormDialog,
  DeviceListTable,
  YingdaoApplicationsDrawer,
  useDeviceManagement,
} from '@/features/device-management'
import { useThemeStore } from '@/stores/theme'
import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'
import PageSection from '@/shared/components/PageSection.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'

const management = useDeviceManagement()
const themeStore = useThemeStore()
const { resolvedTheme } = storeToRefs(themeStore)
const search = ref('')
const { viewMode } = useDeviceOfficeView()
const DeviceOfficeStage = defineAsyncComponent(
  () => import('@/features/device-office/ui/DeviceOfficeStage.vue'),
)

const visibleRows = computed(() => {
  const keyword = search.value.trim().toLocaleLowerCase()
  if (!keyword) return management.rows.value
  return management.rows.value.filter((device) =>
    [device.deviceName, device.deviceId, device.location].some((value) =>
      value.toLocaleLowerCase().includes(keyword),
    ),
  )
})
const stations = computed(() => createOfficeStations(visibleRows.value))

function openStation(station: OfficeStationViewModel): void {
  if (station.device) management.openDetail(station.device)
}
</script>

<template>
  <div class="page-container device-center-page">
    <DeviceOfficeToolbar
      v-model:search="search"
      v-model:view-mode="viewMode"
      :total="management.statistics.value.total"
      :online="management.statistics.value.online"
      :offline="management.statistics.value.offline"
      :loading="management.listLoading.value"
      @refresh="management.retryList"
      @add="management.openCreate"
    />

    <LoadingState
      v-if="management.listLoading.value"
      class="device-center-page__state"
      description="正在布置设备办公区…"
    />
    <ErrorState
      v-else-if="management.listError.value"
      class="device-center-page__state"
      :description="management.listError.value"
      retryable
      @retry="management.retryList"
    />
    <template v-else-if="viewMode === 'office'">
      <DeviceOfficeStage
        :stations="stations"
        :resolved-theme="resolvedTheme"
        @select="openStation"
      />
      <PaginationBar
        v-model:page="management.page.value"
        :page-size="management.pageSize.value"
        :page-sizes="[9]"
        :item-count="management.total.value"
        @update:page-size="management.setPageSize"
      />
    </template>
    <PageSection v-else fill>
      <div class="device-list-pattern">
        <DeviceListTable
          :rows="visibleRows"
          @view="management.openDetail"
          @edit="management.openEdit"
          @retry="management.retryList"
        />
        <PaginationBar
          v-model:page="management.page.value"
          :page-size="management.pageSize.value"
          :page-sizes="[9]"
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
      :yingdao-inventory="management.yingdaoInventory.value"
      :provider-inventory-loading="management.providerInventoryLoading.value"
      :provider-inventory-error="management.providerInventoryError.value"
      :yingdao-refreshing="management.yingdaoRefreshing.value"
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
.device-list-pattern {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-4);
}

.device-center-page {
  height: 100%;
  min-height: 0;
}

.device-center-page__state {
  min-height: 420px;
  flex: 1;
}

.device-center-page :deep(.pagination-bar) {
  flex: none;
}
</style>
