<script setup lang="ts">
import { Icon as VanIcon, Tag as VanTag } from 'vant'
import { computed } from 'vue'

import {
  DEVICE_CONNECTION_META,
  formatRelativeHeartbeat,
  getDeviceConnectionDisplayState,
  type Device,
} from '@/entities/device'
import { TASK_STATUS_META } from '@/entities/task'

import type { DeviceActiveTaskState } from '../model/use-device-active-task'

const props = defineProps<{
  device: Device
  activeTaskState: DeviceActiveTaskState
}>()

const emit = defineEmits<{
  selectDevice: [deviceId: string]
}>()

const heartbeatText = computed(() =>
  formatRelativeHeartbeat(props.device.workerRuntime?.lastSeenAt ?? null),
)
const updateText = computed(() =>
  heartbeatText.value === '—' ? '未上报' : heartbeatText.value,
)
const connectionLabel = computed(
  () =>
    DEVICE_CONNECTION_META[
      getDeviceConnectionDisplayState(
        props.device.workerRuntime?.connectionStatus,
      )
    ].label,
)
const primaryStatus = computed(() => {
  if (!props.device.enabled) {
    return { label: '停用', tagType: 'warning' as const }
  }
  if (props.activeTaskState.initialLoading) {
    return { label: '加载中', tagType: 'default' as const }
  }
  if (props.activeTaskState.initialError) {
    return { label: '—', tagType: 'default' as const }
  }
  if (props.activeTaskState.task) {
    return TASK_STATUS_META[props.activeTaskState.task.status]
  }
  if (props.activeTaskState.task === null) {
    return { label: '空闲', tagType: 'default' as const }
  }
  return { label: '—', tagType: 'default' as const }
})
</script>

<template>
  <article
    class="device-list-card mobile-card mobile-press-surface"
    data-testid="device-card"
  >
    <button
      type="button"
      class="device-list-card__main"
      :aria-label="`查看设备：${device.displayName}`"
      @click="emit('selectDevice', device.deviceId)"
    />

    <span
      class="device-list-card__leading"
      data-testid="device-card-leading"
      aria-hidden="true"
    >
      <VanIcon name="desktop-o" />
    </span>

    <span class="device-list-card__content">
      <strong class="device-list-card__name" data-testid="device-card-name">
        {{ device.displayName }}
      </strong>
      <span class="device-list-card__runtime" data-testid="device-card-runtime">
        {{ connectionLabel }}
      </span>
      <span class="device-list-card__meta" data-testid="device-card-meta">
        <span>{{ updateText }}</span>
        <span aria-hidden="true">·</span>
        <span>Worker {{ device.workerRuntime?.workerVersion || '—' }}</span>
      </span>
    </span>

    <span class="device-list-card__trailing">
      <VanTag
        :type="primaryStatus.tagType"
        round
        data-testid="device-card-status"
      >
        {{ primaryStatus.label }}
      </VanTag>
      <VanIcon
        class="device-list-card__chevron"
        name="arrow"
        data-testid="device-card-chevron"
        aria-hidden="true"
      />
    </span>
  </article>
</template>

<style scoped>
.device-list-card {
  position: relative;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  width: 100%;
  min-width: 0;
  column-gap: var(--space-2);
  padding: var(--layout-card-padding);
  align-items: center;
  color: inherit;
  text-align: left;
}

.device-list-card__main {
  position: absolute;
  z-index: 1;
  inset: 0;
  padding: 0;
  background: transparent;
  border: 0;
  border-radius: var(--radius-card);
}

.device-list-card__main:focus-visible {
  outline: var(--focus-ring-width) solid var(--focus-ring-color);
  outline-offset: var(--focus-ring-offset);
}

.device-list-card:has(.device-list-card__main:active) {
  transform: scale(var(--press-scale-card));
  background: var(--bg-surface-pressed);
  border-color: var(--border-default);
  box-shadow: var(--shadow-card-pressed);
}

.device-list-card__leading {
  display: grid;
  width: var(--layout-card-leading-icon-slot-width);
  flex: none;
  align-self: center;
  color: var(--text-secondary);
  font-size: var(--icon-size-card-leading);
  place-items: center;
}

.device-list-card__content {
  display: grid;
  min-width: 0;
  gap: var(--layout-card-row-gap);
}

.device-list-card__name,
.device-list-card__runtime,
.device-list-card__meta {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-list-card__name {
  font-size: var(--font-size-label);
  line-height: var(--line-height-label);
}

.device-list-card__runtime {
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
  line-height: var(--line-height-secondary);
}

.device-list-card__meta {
  display: flex;
  gap: var(--space-1);
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

.device-list-card__meta span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-list-card__trailing {
  display: grid;
  min-width: 0;
  align-self: stretch;
  grid-template-rows: repeat(3, minmax(0, 1fr));
  justify-items: end;
}

.device-list-card__trailing .van-tag {
  grid-row: 1;
  align-self: start;
}

.device-list-card__chevron {
  display: grid;
  width: var(--layout-card-trailing-icon-slot-width);
  grid-row: 2;
  align-self: center;
  justify-self: end;
  color: var(--text-tertiary);
  font-size: var(--icon-size-card-chevron);
  place-items: center;
}
</style>
