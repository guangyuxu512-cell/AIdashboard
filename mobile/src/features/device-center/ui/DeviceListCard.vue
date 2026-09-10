<script setup lang="ts">
import { computed } from 'vue'

import {
  DeviceStatusArtwork,
  formatRelativeHeartbeat,
  type Device,
} from '@/entities/device'
import { MobileIcon } from '@/shared/icons'
import { MobileBusinessCardFrame } from '@/shared/ui'

import {
  DEVICE_VISUAL_STATE_LABELS,
  getDeviceVisualState,
} from '../model/device-visual'
import type { DeviceActiveTaskState } from '../model/use-device-active-task'

const props = defineProps<{
  device: Device
  activeTaskState: DeviceActiveTaskState
}>()

const emit = defineEmits<{
  selectDevice: [deviceId: string]
}>()

const visualState = computed(() =>
  getDeviceVisualState(props.device, props.activeTaskState),
)
const visualStateLabel = computed(
  () => DEVICE_VISUAL_STATE_LABELS[visualState.value],
)
const heartbeatText = computed(() =>
  formatRelativeHeartbeat(props.device.workerRuntime?.lastSeenAt ?? null),
)
const heartbeatMeta = computed(() =>
  heartbeatText.value === '—' ? '心跳未上报' : `心跳 ${heartbeatText.value}`,
)
const enabledMeta = computed(() => (props.device.enabled ? '已启用' : '已停用'))
</script>

<template>
  <MobileBusinessCardFrame
    class="device-list-card"
    :class="`device-list-card--${visualState}`"
    :label="`查看设备：${device.displayName}`"
    chevron-test-id="device-card-chevron"
    data-testid="device-card"
    @activate="emit('selectDevice', device.deviceId)"
  >
    <template #leading>
      <span class="device-list-card__leading" data-testid="device-card-leading">
        <DeviceStatusArtwork kind="desktop" :state="visualState" />
      </span>
    </template>

    <template #title>
      <span class="device-list-card__name" data-testid="device-card-name">
        {{ device.displayName }}
      </span>
    </template>

    <template #status>
      <span
        class="device-list-card__runtime"
        :class="`device-list-card__runtime--${visualState}`"
        data-testid="device-card-runtime"
      >
        <i class="device-list-card__state-dot" aria-hidden="true" />
        <span>{{ visualStateLabel }}</span>
      </span>
    </template>

    <template #meta>
      <span class="device-list-card__meta" data-testid="device-card-meta">
        <MobileIcon class="device-list-card__heartbeat" name="heartbeat" />
        <span>{{ heartbeatMeta }}</span>
        <span aria-hidden="true">·</span>
        <span>{{ enabledMeta }}</span>
      </span>
    </template>
  </MobileBusinessCardFrame>
</template>

<style scoped>
.device-list-card__leading {
  display: flex;
  width: 100%;
  height: 100%;
  align-items: center;
  justify-content: center;
  transform: translateX(var(--device-list-artwork-offset-x));
}

.device-list-card {
  color: var(--device-list-text-primary);
  backdrop-filter: blur(var(--visual-v2-business-card-blur));
}

.device-list-card__name {
  display: block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-list-card__runtime,
.device-list-card__meta {
  display: flex;
  min-width: 0;
  overflow: hidden;
  align-items: center;
  white-space: nowrap;
}

.device-list-card__runtime {
  gap: var(--visual-v2-business-card-inline-gap);
}

.device-list-card__runtime--online {
  color: var(--device-list-status-online);
}

.device-list-card__runtime--running {
  color: var(--device-list-status-running);
}

.device-list-card__runtime--offline {
  color: var(--device-list-status-offline);
}

.device-list-card__runtime--unreported {
  color: var(--text-secondary);
}

.device-list-card__state-dot {
  width: var(--device-list-status-dot-size);
  height: var(--device-list-status-dot-size);
  flex: none;
  background: currentcolor;
  border-radius: 50%;
}

.device-list-card__meta {
  gap: var(--visual-v2-business-card-inline-gap);
  color: var(--visual-v2-business-card-meta-color);
}

.device-list-card__heartbeat {
  width: var(--visual-v2-business-card-meta-icon-size);
  height: var(--visual-v2-business-card-meta-icon-size);
  flex: none;
  font-size: var(--visual-v2-business-card-meta-icon-size);
}

.device-list-card__meta span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
