<script setup lang="ts">
import { Button as VanButton, Loading as VanLoading, Tag as VanTag } from 'vant'
import { computed } from 'vue'

import {
  DeviceConnectionTag,
  DeviceEnabledTag,
  formatRelativeHeartbeat,
  type Device,
  type DeviceProviderInventoryReadDto,
  YINGDAO_PROVIDER_STATUS_META,
} from '@/entities/device'

const props = defineProps<{
  device: Device
  inventories: DeviceProviderInventoryReadDto[] | undefined
  providerLoading: boolean
  providerError: boolean
}>()

const emit = defineEmits<{ retryProvider: [] }>()

const yingdao = computed(() =>
  props.inventories?.find((item) => item.provider_code === 'yingdao'),
)
const runtimeMeta = computed(() => {
  const runtime = props.device.workerRuntime
  if (!runtime) return 'Worker — · 未上报'
  return `Worker ${runtime.workerVersion || '—'} · ${formatRelativeHeartbeat(runtime.lastSeenAt)}`
})
</script>

<template>
  <section
    class="device-yingdao-summary mobile-card"
    data-testid="device-detail"
    aria-label="设备与影刀摘要"
  >
    <div
      class="device-yingdao-summary__column"
      data-testid="device-summary-device"
    >
      <span class="device-yingdao-summary__label">设备</span>
      <strong class="device-yingdao-summary__value">
        {{ device.displayName }}
      </strong>
      <div class="device-yingdao-summary__tags">
        <DeviceConnectionTag :status="device.workerRuntime?.connectionStatus" />
        <DeviceEnabledTag :enabled="device.enabled" />
      </div>
      <p class="device-yingdao-summary__meta">{{ runtimeMeta }}</p>
    </div>

    <div
      class="device-yingdao-summary__column"
      data-testid="device-summary-yingdao"
      :aria-busy="providerLoading"
    >
      <span class="device-yingdao-summary__label">影刀账号</span>

      <template v-if="providerLoading">
        <VanLoading size="var(--icon-size-small)">加载中</VanLoading>
      </template>
      <template v-else-if="providerError">
        <strong class="device-yingdao-summary__value">加载失败</strong>
        <VanButton
          class="device-yingdao-summary__retry"
          @click="emit('retryProvider')"
        >
          重试
        </VanButton>
      </template>
      <template v-else-if="yingdao">
        <strong class="device-yingdao-summary__value">
          {{ yingdao.account_display || '—' }}
        </strong>
        <div class="device-yingdao-summary__tags">
          <VanTag
            :type="
              YINGDAO_PROVIDER_STATUS_META[yingdao.inventory.status].tagType
            "
            round
          >
            {{ YINGDAO_PROVIDER_STATUS_META[yingdao.inventory.status].label }}
          </VanTag>
        </div>
        <p class="device-yingdao-summary__meta">
          {{ yingdao.inventory.provider_version || '—' }}
        </p>
      </template>
      <template v-else>
        <strong class="device-yingdao-summary__value">未上报</strong>
        <p class="device-yingdao-summary__meta">—</p>
      </template>
    </div>
  </section>
</template>

<style scoped>
.device-yingdao-summary {
  display: grid;
  min-width: 0;
  min-height: calc(
    var(--touch-target-min) + var(--touch-target-min) + var(--touch-target-min)
  );
  padding: 0;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  overflow: hidden;
}

.device-yingdao-summary__column {
  display: grid;
  min-width: 0;
  gap: var(--space-1);
  padding: var(--space-4);
  align-content: center;
}

.device-yingdao-summary__column + .device-yingdao-summary__column {
  border-left: var(--border-width) solid var(--border-subtle);
}

.device-yingdao-summary__label,
.device-yingdao-summary__meta {
  min-width: 0;
  overflow: hidden;
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-yingdao-summary__value {
  min-width: 0;
  overflow: hidden;
  font-size: var(--font-size-label);
  line-height: var(--line-height-label);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-yingdao-summary__tags {
  display: flex;
  min-width: 0;
  min-height: var(--line-height-body);
  gap: var(--space-1);
  align-items: center;
  overflow: hidden;
}

.device-yingdao-summary__retry {
  width: max-content;
  min-width: var(--touch-target-min);
  height: var(--touch-target-min);
  padding: 0;
  color: var(--color-primary);
  background: transparent;
  border: 0;
}
</style>
