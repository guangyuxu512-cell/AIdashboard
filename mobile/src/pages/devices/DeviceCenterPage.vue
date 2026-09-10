<script setup lang="ts">
import { showToast } from 'vant'
import { useRouter } from 'vue-router'

import { MOBILE_ROUTE_NAMES } from '@/app/router/routes'
import {
  DeviceInfiniteList,
  DeviceListControls,
  useDeviceCenter,
} from '@/features/device-center'

const router = useRouter()
const deviceCenter = useDeviceCenter()

function openDevice(deviceId: string): void {
  void router.push({
    name: MOBILE_ROUTE_NAMES.deviceDetail,
    params: { deviceId },
  })
}

async function refresh(): Promise<void> {
  if (!(await deviceCenter.refresh())) showToast('刷新失败')
}
</script>

<template>
  <div class="mobile-list-page device-center-page-v2">
    <DeviceListControls
      :overview="deviceCenter.overview.value"
      :filter="deviceCenter.filter.value"
      :search-query="deviceCenter.searchQuery.value"
      :search-available="deviceCenter.searchAvailable.value"
      :filter-preparing="deviceCenter.isFilterPreparing.value"
      @select-filter="deviceCenter.toggleMetricFilter"
      @update-search-query="deviceCenter.setSearchQuery"
    />

    <div
      class="mobile-list-page__scroll mobile-scroll-container"
      data-testid="device-list-scroll"
      aria-label="设备列表"
      tabindex="0"
    >
      <DeviceInfiniteList
        :devices="deviceCenter.filteredDevices.value"
        :active-task-states="deviceCenter.activeTaskStates.value"
        :initial-loading="deviceCenter.isInitialLoading.value"
        :initial-error="deviceCenter.isInitialError.value"
        :filter-preparing="deviceCenter.isFilterPreparing.value"
        :filter-error="deviceCenter.filterPreparationError.value !== null"
        :next-page-error="deviceCenter.isNextPageError.value"
        :refreshing="deviceCenter.refreshing.value"
        :loading-more="deviceCenter.query.isFetchingNextPage.value"
        :has-more="Boolean(deviceCenter.query.hasNextPage.value)"
        @refresh="refresh"
        @retry="deviceCenter.query.refetch"
        @load-more="deviceCenter.loadMore"
        @retry-load-more="deviceCenter.retryLoadMore"
        @retry-filter="deviceCenter.retryFilterPreparation"
        @select-device="openDevice"
      />
    </div>
  </div>
</template>

<style scoped>
.device-center-page-v2 {
  color: var(--device-list-text-primary);
}
</style>
