<script setup lang="ts">
import { showToast } from 'vant'
import { useRouter } from 'vue-router'

import { MOBILE_ROUTE_NAMES } from '@/app/router/routes'
import {
  DeviceInfiniteList,
  DeviceOverviewCards,
  useDeviceCenter,
} from '@/features/device-center'
import { MobileListToolbar } from '@/shared/ui'

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
  <div class="mobile-list-page">
    <DeviceOverviewCards :overview="deviceCenter.overview.value" />

    <MobileListToolbar
      title="设备"
      :meta="
        deviceCenter.total.value === undefined
          ? '—'
          : `${deviceCenter.total.value} 台`
      "
    />

    <div class="mobile-list-page__scroll" data-testid="device-list-scroll">
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
  </div>
</template>
