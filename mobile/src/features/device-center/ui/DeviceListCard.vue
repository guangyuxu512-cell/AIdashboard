<script setup lang="ts">
import { computed } from 'vue'

import {
  DeviceConnectionTag,
  DeviceEnabledTag,
  formatRelativeHeartbeat,
  type Device,
} from '@/entities/device'

import type { DeviceActiveTaskState } from '../model/use-device-active-task'
import ActiveTaskSummary from './ActiveTaskSummary.vue'

const props = defineProps<{
  device: Device
  activeTaskState: DeviceActiveTaskState
}>()

const emit = defineEmits<{
  selectDevice: [deviceId: string]
  selectTask: [taskId: string]
}>()

const heartbeatText = computed(() =>
  formatRelativeHeartbeat(props.device.workerRuntime?.lastSeenAt ?? null),
)
const updateText = computed(() =>
  heartbeatText.value === '—' ? '心跳未上报' : `${heartbeatText.value}更新`,
)
</script>

<template>
  <article class="device-list-card" data-testid="device-card">
    <button
      type="button"
      class="device-list-card__main"
      :aria-label="`查看设备：${device.displayName}`"
      @click="emit('selectDevice', device.deviceId)"
    >
      <span class="device-list-card__heading">
        <strong>{{ device.displayName }}</strong>
        <span class="device-list-card__tags">
          <DeviceEnabledTag :enabled="device.enabled" />
          <DeviceConnectionTag
            :status="device.workerRuntime?.connectionStatus"
          />
        </span>
      </span>
    </button>

    <ActiveTaskSummary
      :task="activeTaskState.task"
      :initial-loading="activeTaskState.initialLoading"
      :initial-error="activeTaskState.initialError"
      :background-error="activeTaskState.backgroundError"
      :error-message="activeTaskState.errorMessage"
      compact
      @retry="activeTaskState.retry"
      @select="emit('selectTask', $event)"
    />

    <p class="device-list-card__meta">
      {{ updateText }} · Worker
      {{ device.workerRuntime?.workerVersion || '—' }}
    </p>
  </article>
</template>

<style scoped>
.device-list-card {
  display: grid;
  min-width: 0;
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--bg-surface);
  border: var(--border-width) solid var(--border-default);
  border-radius: var(--radius-card);
}

.device-list-card__main {
  display: grid;
  width: 100%;
  min-width: 0;
  min-height: var(--touch-target-min);
  gap: var(--space-1);
  padding: 0;
  color: inherit;
  text-align: left;
  background: none;
  border: 0;
}

.device-list-card__main:focus-visible {
  outline: var(--focus-ring-width) solid var(--focus-ring-color);
  outline-offset: var(--focus-ring-offset);
}

.device-list-card__heading,
.device-list-card__tags {
  display: flex;
  min-width: 0;
  gap: var(--space-2);
  align-items: flex-start;
  justify-content: space-between;
}

.device-list-card__heading strong {
  min-width: 0;
  overflow: hidden;
  font-size: var(--font-size-label);
  line-height: var(--line-height-label);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-list-card__tags {
  flex: none;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.device-list-card__meta {
  min-width: 0;
  overflow: hidden;
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
