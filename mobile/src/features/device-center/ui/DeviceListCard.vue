<script setup lang="ts">
import { computed } from 'vue'

import {
  DeviceConnectionTag,
  DeviceEnabledTag,
  formatRelativeHeartbeat,
  type Device,
} from '@/entities/device'

import { useDeviceActiveTask } from '../model/use-device-active-task'
import ActiveTaskSummary from './ActiveTaskSummary.vue'

const props = defineProps<{ device: Device }>()

const emit = defineEmits<{
  selectDevice: [deviceId: string]
  selectTask: [taskId: string]
}>()

const activeTask = useDeviceActiveTask(() => props.device.deviceId)
const heartbeatText = computed(() =>
  formatRelativeHeartbeat(props.device.workerRuntime?.lastSeenAt ?? null),
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
      <span class="device-list-card__meta">
        <span>版本 {{ device.workerRuntime?.workerVersion || '—' }}</span>
        <span>心跳 {{ heartbeatText }}</span>
      </span>
    </button>

    <ActiveTaskSummary
      :task="activeTask.query.data.value"
      :initial-loading="activeTask.isInitialLoading.value"
      :initial-error="activeTask.isInitialError.value"
      :background-error="activeTask.isBackgroundError.value"
      :error-message="activeTask.errorMessage.value"
      compact
      @retry="activeTask.query.refetch"
      @select="emit('selectTask', $event)"
    />
  </article>
</template>

<style scoped>
.device-list-card {
  display: grid;
  min-width: 0;
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--bg-surface);
  border: var(--border-width) solid var(--border-subtle);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-surface);
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

.device-list-card__heading,
.device-list-card__tags,
.device-list-card__meta {
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
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

.device-list-card__meta span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-list-card__meta span:last-child {
  flex: none;
}
</style>
