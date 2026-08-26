<script setup lang="ts">
import { showToast } from 'vant'
import { useRouter } from 'vue-router'

import { MOBILE_ROUTE_NAMES } from '@/app/router/routes'
import {
  DeviceInfiniteList,
  DeviceOverviewCards,
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

function openTask(taskId: string, sourceDeviceId: string): void {
  void router.push({
    name: MOBILE_ROUTE_NAMES.taskDetail,
    params: { taskId },
    query: { fromDeviceId: sourceDeviceId },
  })
}

async function refresh(): Promise<void> {
  if (!(await deviceCenter.refresh())) showToast('刷新失败')
}
</script>

<template>
  <div class="device-center-page">
    <DeviceOverviewCards
      v-if="!deviceCenter.isInitialError.value"
      :overview="deviceCenter.overview.value"
    />

    <div
      v-if="deviceCenter.total.value !== undefined"
      class="device-center-page__toolbar"
    >
      <p>{{ deviceCenter.total.value }} 台设备</p>
    </div>

    <DeviceInfiniteList
      :devices="deviceCenter.devices.value"
      :active-task-states="deviceCenter.activeTaskStates.value"
      :initial-loading="deviceCenter.isInitialLoading.value"
      :initial-error="deviceCenter.isInitialError.value"
      :next-page-error="deviceCenter.isNextPageError.value"
      :refreshing="deviceCenter.refreshing.value"
      :loading-more="deviceCenter.query.isFetchingNextPage.value"
      :has-more="Boolean(deviceCenter.query.hasNextPage.value)"
      @refresh="refresh"
      @retry="deviceCenter.query.refetch"
      @load-more="deviceCenter.loadMore"
      @retry-load-more="deviceCenter.retryLoadMore"
      @select-device="openDevice"
      @select-task="openTask"
    />
  </div>
</template>

<style scoped>
.device-center-page {
  min-height: 100%;
}

.device-center-page__toolbar {
  display: flex;
  min-height: var(--touch-target-min);
  padding: var(--space-2)
    max(var(--layout-page-padding-x), var(--safe-area-right)) var(--space-2)
    max(var(--layout-page-padding-x), var(--safe-area-left));
  align-items: center;
  justify-content: space-between;
  color: var(--text-secondary);
  background: var(--bg-app);
}
</style>
