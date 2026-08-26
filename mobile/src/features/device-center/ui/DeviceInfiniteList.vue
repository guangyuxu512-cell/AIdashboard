<script setup lang="ts">
import {
  Button as VanButton,
  Empty as VanEmpty,
  List as VanList,
  NoticeBar as VanNoticeBar,
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
  backgroundError: boolean
  nextPageError: boolean
  errorMessage: string
  refreshing: boolean
  loadingMore: boolean
  hasMore: boolean
}>()

const pendingActiveTaskState: DeviceActiveTaskState = {
  task: undefined,
  hasSuccessfulData: false,
  initialLoading: true,
  initialError: false,
  backgroundError: false,
  errorMessage: '当前任务加载失败',
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
  selectTask: [taskId: string, deviceId: string]
}>()
</script>

<template>
  <div
    v-if="backgroundError"
    class="device-list__background-error"
    data-testid="device-background-error"
  >
    <VanNoticeBar
      class="mobile-notice-bar--warning"
      :text="`${errorMessage}，当前展示上次成功加载的数据`"
      wrapable
    />
  </div>

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
    <VanEmpty image="error" :description="errorMessage">
      <VanButton type="primary" @click="emit('retry')">重新加载</VanButton>
    </VanEmpty>
  </div>

  <VanPullRefresh v-else :model-value="refreshing" @refresh="emit('refresh')">
    <VanEmpty
      v-if="devices.length === 0"
      description="暂无设备"
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
          @select-task="emit('selectTask', $event, device.deviceId)"
        />
      </div>
      <div
        v-if="nextPageError"
        class="device-list__next-error"
        data-testid="device-list-next-page-error"
      >
        <VanNoticeBar
          class="mobile-notice-bar--warning"
          :text="`${errorMessage}，已保留当前设备`"
          wrapable
        />
        <VanButton block @click="emit('retryLoadMore')">
          重试加载更多
        </VanButton>
      </div>
    </VanList>
  </VanPullRefresh>
</template>

<style scoped>
.device-list-state {
  display: grid;
  min-height: var(--layout-page-state-min-height);
  gap: var(--space-4);
  padding: var(--space-4) max(var(--space-4), var(--safe-area-right))
    var(--space-4) max(var(--space-4), var(--safe-area-left));
  align-content: center;
}

.device-list {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-2)
    max(var(--layout-page-padding-x), var(--safe-area-right)) var(--space-4)
    max(var(--layout-page-padding-x), var(--safe-area-left));
}

.device-list__background-error {
  padding-right: max(var(--layout-page-padding-x), var(--safe-area-right));
  padding-left: max(var(--layout-page-padding-x), var(--safe-area-left));
}

.device-list__next-error {
  display: grid;
  gap: var(--space-2);
  padding: 0 max(var(--layout-page-padding-x), var(--safe-area-right))
    var(--space-4) max(var(--layout-page-padding-x), var(--safe-area-left));
}
</style>
