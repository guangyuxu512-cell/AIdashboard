<script setup lang="ts">
import { computed } from 'vue'

import {
  DeviceStatusArtwork,
  formatRelativeHeartbeat,
  type Device,
  type DeviceProviderInventoryReadDto,
} from '@/entities/device'
import { MobileIcon, type MobileIconName } from '@/shared/icons'

import {
  getDeviceRuntimeDisplayLabel,
  getDeviceVisualState,
} from '../model/device-visual'
import type { DeviceActiveTaskState } from '../model/use-device-active-task'

const props = defineProps<{
  device: Device
  activeTaskState: DeviceActiveTaskState
  inventories: DeviceProviderInventoryReadDto[] | undefined
}>()

const visualState = computed(() =>
  getDeviceVisualState(props.device, props.activeTaskState),
)
const runtimeLabel = computed(() =>
  getDeviceRuntimeDisplayLabel(props.device, props.activeTaskState),
)
const heartbeatText = computed(() =>
  formatRelativeHeartbeat(props.device.workerRuntime?.lastSeenAt ?? null),
)
const heartbeatLabel = computed(() =>
  heartbeatText.value === '—'
    ? '心跳未上报'
    : `最后心跳：${heartbeatText.value}`,
)
const yingdaoVersion = computed(() => {
  const inventory = props.inventories?.find(
    (item) => item.provider_code === 'yingdao',
  )
  return inventory?.provider_version ?? inventory?.inventory.provider_version
})
const metaItems = computed<
  Array<{ key: string; icon: MobileIconName; label: string }>
>(() => {
  const items: Array<{ key: string; icon: MobileIconName; label: string }> = []
  const workerVersion = props.device.workerRuntime?.workerVersion.trim()
  if (workerVersion) {
    items.push({
      key: 'worker',
      icon: 'runtime-device',
      label: `Worker ${workerVersion}`,
    })
  }
  if (yingdaoVersion.value) {
    items.push({
      key: 'yingdao',
      icon: 'automation',
      label: `影刀 ${yingdaoVersion.value}`,
    })
  }
  return items
})
</script>

<template>
  <section
    class="device-detail-hero"
    :class="`device-detail-hero--${visualState}`"
    data-testid="device-detail-hero"
    aria-label="设备概览"
  >
    <div class="device-detail-hero__main">
      <div class="device-detail-hero__artwork">
        <DeviceStatusArtwork
          kind="desktop"
          :state="visualState"
          variant="hero"
        />
      </div>

      <div class="device-detail-hero__content">
        <h1 class="device-detail-hero__name" data-testid="device-hero-name">
          {{ device.displayName }}
        </h1>
        <div
          class="device-detail-hero__status"
          data-testid="device-hero-status"
        >
          <i class="device-detail-hero__status-dot" aria-hidden="true" />
          <span>{{ runtimeLabel }}</span>
        </div>
        <p
          class="device-detail-hero__heartbeat"
          data-testid="device-hero-heartbeat"
        >
          {{ heartbeatLabel }}
        </p>
      </div>
    </div>

    <div
      v-if="metaItems.length > 0"
      class="device-detail-hero__meta"
      :class="{ 'device-detail-hero__meta--single': metaItems.length === 1 }"
      data-testid="device-hero-meta"
    >
      <div
        v-for="item in metaItems"
        :key="item.key"
        class="device-detail-hero__meta-item"
      >
        <MobileIcon class="device-detail-hero__meta-icon" :name="item.icon" />
        <span>{{ item.label }}</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.device-detail-hero {
  min-width: 0;
  min-height: var(--visual-v2-detail-hero-min-height);
  padding: var(--visual-v2-detail-hero-padding-top)
    var(--visual-v2-detail-hero-padding-right)
    var(--visual-v2-detail-hero-padding-bottom)
    var(--visual-v2-detail-hero-padding-left);
  color: var(--visual-v2-page-text-primary);
  background: var(--visual-v2-detail-surface-background);
  border: var(--visual-v2-business-card-border-width) solid
    var(--visual-v2-detail-surface-border-color);
  border-radius: var(--visual-v2-metric-strip-radius);
  box-shadow: var(--visual-v2-detail-surface-shadow);
}

.device-detail-hero__main {
  display: grid;
  min-width: 0;
  gap: var(--visual-v2-detail-hero-main-gap);
  grid-template-columns: var(--visual-v2-detail-hero-leading-column) minmax(
      0,
      1fr
    );
  align-items: center;
}

.device-detail-hero__artwork {
  display: flex;
  height: var(--visual-v2-detail-hero-artwork-height);
  align-items: center;
  justify-content: center;
}

.device-detail-hero__content {
  min-width: 0;
}

.device-detail-hero__name {
  margin: 0 0 var(--visual-v2-detail-hero-title-gap);
  overflow: hidden;
  font-size: var(--typography-v2-detail-hero-title-size);
  font-weight: var(--typography-v2-detail-hero-title-weight);
  line-height: var(--typography-v2-detail-hero-title-line-height);
  letter-spacing: var(--typography-v2-detail-hero-title-letter-spacing);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-detail-hero__status {
  display: flex;
  gap: var(--visual-v2-detail-hero-status-gap);
  margin-bottom: var(--visual-v2-detail-hero-status-bottom-gap);
  align-items: center;
  font-size: var(--typography-v2-detail-hero-status-size);
  font-weight: var(--typography-v2-detail-hero-status-weight);
  line-height: var(--typography-v2-detail-hero-status-line-height);
}

.device-detail-hero--online .device-detail-hero__status {
  color: var(--visual-v2-detail-status-online);
}

.device-detail-hero--running .device-detail-hero__status {
  color: var(--visual-v2-detail-status-running);
}

.device-detail-hero--offline .device-detail-hero__status {
  color: var(--visual-v2-detail-status-offline);
}

.device-detail-hero__status-dot {
  width: var(--visual-v2-detail-hero-status-dot-size);
  height: var(--visual-v2-detail-hero-status-dot-size);
  flex: none;
  background: currentcolor;
  border-radius: var(--radius-round);
}

.device-detail-hero__heartbeat {
  overflow: hidden;
  color: var(--visual-v2-detail-meta-color);
  font-size: var(--typography-v2-detail-hero-meta-size);
  font-weight: var(--typography-v2-detail-hero-meta-weight);
  line-height: var(--typography-v2-detail-hero-meta-line-height);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-detail-hero__meta {
  display: grid;
  min-width: 0;
  gap: var(--visual-v2-detail-hero-meta-gap);
  margin-top: var(--visual-v2-detail-hero-meta-top-gap);
  padding-top: var(--visual-v2-detail-hero-meta-padding-top);
  border-top: var(--visual-v2-business-card-border-width) solid
    var(--visual-v2-detail-divider-color);
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.device-detail-hero__meta--single {
  grid-template-columns: minmax(0, 1fr);
}

.device-detail-hero__meta-item {
  display: flex;
  min-width: 0;
  gap: var(--visual-v2-detail-hero-meta-inline-gap);
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  font-size: var(--typography-v2-meta-size);
  font-weight: var(--typography-v2-meta-weight);
  line-height: var(--typography-v2-meta-line-height);
  white-space: nowrap;
}

.device-detail-hero__meta-item span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.device-detail-hero__meta-icon {
  width: var(--visual-v2-detail-hero-meta-icon-size);
  height: var(--visual-v2-detail-hero-meta-icon-size);
  font-size: var(--visual-v2-detail-hero-meta-icon-size);
}
</style>
