<script setup lang="ts">
import { computed } from 'vue'

import {
  DeviceStatusArtwork,
  formatRelativeHeartbeat,
  type Device,
} from '@/entities/device'
import { MobileIcon } from '@/shared/icons'

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
  <article
    class="device-list-card mobile-press-surface"
    :class="`device-list-card--${visualState}`"
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
      <DeviceStatusArtwork kind="desktop" :state="visualState" />
    </span>

    <span class="device-list-card__content">
      <strong class="device-list-card__name" data-testid="device-card-name">
        {{ device.displayName }}
      </strong>
      <span
        class="device-list-card__runtime"
        :class="`device-list-card__runtime--${visualState}`"
        data-testid="device-card-runtime"
      >
        <i class="device-list-card__state-dot" aria-hidden="true" />
        <span>{{ visualStateLabel }}</span>
      </span>
      <span class="device-list-card__meta" data-testid="device-card-meta">
        <span>{{ heartbeatMeta }}</span>
        <span aria-hidden="true">·</span>
        <span>{{ enabledMeta }}</span>
      </span>
    </span>

    <MobileIcon
      class="device-list-card__chevron"
      name="chevron-right"
      data-testid="device-card-chevron"
    />
  </article>
</template>

<style scoped>
.device-list-card {
  position: relative;
  display: grid;
  width: 100%;
  min-width: 0;
  min-height: var(--device-list-card-min-height);
  padding: var(--device-list-card-padding-top)
    var(--device-list-card-padding-right) var(--device-list-card-padding-bottom)
    var(--device-list-card-padding-left);
  overflow: hidden;
  color: var(--device-list-text-primary);
  text-align: left;
  background: var(--device-list-card-background);
  border: var(--device-list-card-border-width) solid
    var(--device-list-card-border);
  border-radius: var(--device-list-card-radius);
  box-shadow: var(--device-list-card-shadow);
  grid-template-columns:
    var(--device-list-card-artwork-column) minmax(0, 1fr)
    var(--device-list-card-chevron-column);
  align-items: center;
}

.device-list-card__main {
  position: absolute;
  z-index: 2;
  inset: 0;
  padding: 0;
  background: transparent;
  border: 0;
  border-radius: var(--device-list-card-radius);
}

.device-list-card__main:focus-visible {
  outline: var(--focus-ring-width) solid var(--focus-ring-color);
  outline-offset: calc(var(--focus-ring-offset) * -1);
}

.device-list-card:has(.device-list-card__main:active) {
  background: var(--device-list-card-pressed-background);
  border-color: var(--device-list-card-pressed-border);
  box-shadow: var(--device-list-card-pressed-shadow);
  transform: scale(var(--press-scale-card));
}

.device-list-card__leading {
  position: relative;
  z-index: 1;
  display: flex;
  height: var(--device-list-artwork-height);
  align-items: center;
  justify-content: center;
  transform: translateX(var(--device-list-artwork-offset-x));
}

.device-list-card__content {
  position: relative;
  z-index: 1;
  display: block;
  min-width: 0;
}

.device-list-card__name,
.device-list-card__runtime,
.device-list-card__meta {
  min-width: 0;
}

.device-list-card__name {
  display: block;
  margin: 0 0 var(--device-list-card-name-gap);
  overflow: hidden;
  font-size: var(--device-list-card-name-size);
  font-weight: var(--device-list-card-name-weight);
  line-height: var(--device-list-card-name-line-height);
  letter-spacing: var(--device-list-card-name-letter-spacing);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-list-card__runtime,
.device-list-card__meta {
  display: flex;
  overflow: hidden;
  align-items: center;
  white-space: nowrap;
}

.device-list-card__runtime {
  gap: var(--device-list-card-inline-gap);
  margin-bottom: var(--device-list-card-status-gap);
  font-size: var(--device-list-card-status-size);
  font-weight: var(--device-list-card-status-weight);
  line-height: var(--device-list-card-status-line-height);
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
  color: var(--device-list-status-unreported);
}

.device-list-card__state-dot {
  width: var(--device-list-status-dot-size);
  height: var(--device-list-status-dot-size);
  flex: none;
  background: currentcolor;
  border-radius: 50%;
}

.device-list-card__meta {
  gap: var(--device-list-card-inline-gap);
  color: var(--device-list-card-meta-color);
  font-size: var(--device-list-card-meta-size);
  font-weight: var(--device-list-card-meta-weight);
  line-height: var(--device-list-card-meta-line-height);
}

.device-list-card__meta span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-list-card__chevron {
  position: relative;
  z-index: 1;
  width: var(--device-list-card-chevron-size);
  height: var(--device-list-card-chevron-size);
  color: var(--device-list-card-chevron-color);
  font-size: var(--device-list-card-chevron-size);
  justify-self: end;
}
</style>
