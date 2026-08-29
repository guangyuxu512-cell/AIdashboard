<script setup lang="ts">
import {
  Button as VanButton,
  Empty as VanEmpty,
  List as VanList,
  PullRefresh as VanPullRefresh,
  Skeleton as VanSkeleton,
} from 'vant'

import type { Device } from '@/entities/device'

import type { DeviceActiveTaskState } from '../model/use-device-active-task'
import DeviceListCard from './DeviceListCard.vue'

const props = defineProps<{
  devices: Device[]
  activeTaskStates: Readonly<Record<string, DeviceActiveTaskState>>
  initialLoading: boolean
  initialError: boolean
  nextPageError: boolean
  refreshing: boolean
  loadingMore: boolean
  hasMore: boolean
}>()

const pendingActiveTaskState: DeviceActiveTaskState = {
  task: undefined,
  hasSuccessfulData: false,
  initialLoading: false,
  initialError: false,
  backgroundError: false,
  retry: () => undefined,
}

function activeTaskState(deviceId: string): DeviceActiveTaskState {
  return props.activeTaskStates[deviceId] ?? pendingActiveTaskState
}

const emit = defineEmits<{
  refresh: []
  retry: []
  loadMore: []
  retryLoadMore: []
  selectDevice: [deviceId: string]
}>()
</script>

<template>
  <div
    v-if="initialLoading"
    class="device-list-state"
    data-testid="device-loading"
  >
    <VanSkeleton v-for="index in 3" :key="index" title :row="3" />
  </div>

  <div
    v-else-if="initialError"
    class="device-list-state"
    data-testid="device-error"
  >
    <VanEmpty image="error" description="加载失败">
      <VanButton type="primary" @click="emit('retry')">重试</VanButton>
    </VanEmpty>
  </div>

  <VanPullRefresh
    v-else
    class="device-list-refresh"
    :model-value="refreshing"
    @refresh="emit('refresh')"
  >
    <VanEmpty
      v-if="devices.length === 0"
      description="没有设备"
      data-testid="device-empty"
    />
    <VanList
      v-else
      :loading="loadingMore"
      :finished="!hasMore || nextPageError"
      :finished-text="nextPageError ? '' : '没有更多设备了'"
      @load="emit('loadMore')"
    >
      <div class="device-list" data-testid="device-list">
        <DeviceListCard
          v-for="device in devices"
          :key="device.deviceId"
          :device="device"
          :active-task-state="activeTaskState(device.deviceId)"
          @select-device="emit('selectDevice', $event)"
        />
      </div>
      <div
        v-if="nextPageError"
        class="device-list__next-error"
        data-testid="device-list-next-page-error"
      >
        <span>加载失败</span>
        <VanButton block @click="emit('retryLoadMore')">重试</VanButton>
      </div>
    </VanList>
  </VanPullRefresh>
</template>

<style scoped>
.device-list-state {
  display: grid;
  min-height: 100%;
  gap: var(--space-4);
  padding: var(--space-4) max(var(--space-4), var(--safe-area-right))
    var(--space-4) max(var(--space-4), var(--safe-area-left));
  align-content: center;
}

.device-list-refresh {
  min-height: 100%;
}

.device-list {
  display: grid;
  gap: var(--layout-card-gap);
  padding: var(--layout-content-gap)
    max(var(--layout-page-padding-x), var(--safe-area-right)) var(--space-4)
    max(var(--layout-page-padding-x), var(--safe-area-left));
}

.device-list__next-error {
  display: grid;
  gap: var(--layout-content-gap);
  padding: 0 max(var(--layout-page-padding-x), var(--safe-area-right))
    var(--space-4) max(var(--layout-page-padding-x), var(--safe-area-left));
}
</style>
