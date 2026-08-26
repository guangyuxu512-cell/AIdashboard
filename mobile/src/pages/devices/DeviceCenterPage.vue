<script setup lang="ts">
import { useRouter } from 'vue-router'

import { MOBILE_ROUTE_NAMES } from '@/app/router/routes'
import { DeviceInfiniteList, useDeviceCenter } from '@/features/device-center'

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
</script>

<template>
  <div class="device-center-page">
    <div class="device-center-page__toolbar">
      <p>
        {{
          deviceCenter.total.value === undefined
            ? '设备总数 —'
            : `共 ${deviceCenter.total.value} 台设备`
        }}
      </p>
      <p>每 15 秒刷新</p>
    </div>

    <DeviceInfiniteList
      :devices="deviceCenter.devices.value"
      :initial-loading="deviceCenter.isInitialLoading.value"
      :initial-error="deviceCenter.isInitialError.value"
      :background-error="deviceCenter.isBackgroundError.value"
      :next-page-error="deviceCenter.isNextPageError.value"
      :error-message="deviceCenter.errorMessage.value"
      :refreshing="deviceCenter.refreshing.value"
      :loading-more="deviceCenter.query.isFetchingNextPage.value"
      :has-more="Boolean(deviceCenter.query.hasNextPage.value)"
      @refresh="deviceCenter.refresh"
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

.device-center-page__toolbar p:last-child {
  font-size: var(--font-size-caption);
}
</style>
