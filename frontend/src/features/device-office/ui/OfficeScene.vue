<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import type { ResolvedTheme } from '@/stores/theme'

import {
  checkOfficeAssetAvailability,
  loadOfficeAssetBundle,
} from '../assets/office-asset-loader'
import type { OfficeAssetDefinition } from '../assets/office-asset-manifest'
import type { OfficeStationViewModel } from '../model/types'

defineProps<{
  stations: OfficeStationViewModel[]
  resolvedTheme: ResolvedTheme
}>()

const emit = defineEmits<{ select: [station: OfficeStationViewModel] }>()
const assetState = ref<'checking' | 'missing' | 'invalid' | 'ready'>('checking')
const missingAssets = ref<OfficeAssetDefinition[]>([])
const assetError = ref('')

const stateLabel = {
  empty: '空工位',
  onlineIdle: '在线',
  busy: '执行中',
  offline: '离线',
  error: '异常',
} as const

const missingAssetNames = computed(() =>
  missingAssets.value.map((asset) => asset.url.split('/').at(-1)).join('、'),
)

onMounted(async () => {
  const availability = await checkOfficeAssetAvailability()
  if (!availability.ready) {
    missingAssets.value = availability.missing
    assetState.value = 'missing'
    return
  }
  try {
    await loadOfficeAssetBundle()
    assetState.value = 'ready'
  } catch (error) {
    assetError.value = error instanceof Error ? error.message : '未知资产错误'
    assetState.value = 'invalid'
  }
})
</script>

<template>
  <section
    class="office-scene"
    :class="`office-scene--${resolvedTheme}`"
    aria-label="设备 3D 办公区"
    data-testid="device-office-scene"
    :data-office-assets="assetState"
  >
    <div class="office-scene__asset-state" role="status">
      <template v-if="assetState === 'checking'">
        <strong>正在校验 3D 资产</strong>
      </template>
      <template v-else-if="assetState === 'missing'">
        <strong>正式 3D 资产尚未就绪</strong>
        <span>旧程序化几何体已停用，缺少：{{ missingAssetNames }}</span>
      </template>
      <template v-else-if="assetState === 'invalid'">
        <strong>3D 资产不符合加载契约</strong>
        <span>{{ assetError }}</span>
      </template>
      <template v-else>
        <strong>正式 3D 资产已通过契约校验</strong>
        <span>场景装配将在正式资产评审通过后启用</span>
      </template>
    </div>

    <div class="office-scene__labels" aria-label="办公位设备">
      <button
        v-for="station in stations"
        :key="station.slot"
        type="button"
        class="office-station-label"
        :class="`is-${station.visualState}`"
        :disabled="!station.device"
        :aria-label="
          station.device
            ? `查看设备 ${station.device.deviceName}`
            : `工位 ${station.slot} 空工位`
        "
        @click="station.device && emit('select', station)"
      >
        <i aria-hidden="true" />
        <span>{{ station.device?.deviceName ?? `工位 ${station.slot}` }}</span>
        <span>{{ stateLabel[station.visualState] }}</span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.office-scene {
  position: relative;
  z-index: 0;
  min-height: 520px;
  flex: 1;
  overflow: hidden;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  background: var(--bg-surface-solid);
  box-shadow: var(--shadow-card);
  isolation: isolate;
}

.office-scene__asset-state {
  position: absolute;
  inset: 0;
  display: grid;
  align-content: center;
  justify-items: center;
  gap: var(--space-2);
  padding: var(--space-6);
  color: var(--text-secondary);
  text-align: center;
}

.office-scene__asset-state strong {
  color: var(--text-primary);
  font-size: var(--font-size-section-title);
}

.office-scene__labels {
  position: absolute;
  z-index: 2;
  inset: 25% 11% 7%;
  display: grid;
  align-content: space-between;
  justify-content: space-between;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  grid-template-rows: repeat(3, auto);
  column-gap: 10%;
  pointer-events: none;
}

.office-station-label {
  display: inline-flex;
  min-width: 0;
  max-width: var(--field-width-sm);
  align-items: center;
  align-self: end;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border: 1px solid color-mix(in srgb, var(--border-strong) 72%, transparent);
  border-radius: var(--radius-control);
  background: color-mix(in srgb, var(--bg-surface-solid) 88%, transparent);
  box-shadow: var(--shadow-card);
  color: var(--text-primary);
  font: inherit;
  white-space: nowrap;
  backdrop-filter: blur(var(--glass-blur));
  pointer-events: auto;
}

.office-station-label > span:first-of-type {
  overflow: hidden;
  font-weight: var(--font-weight-medium);
  text-overflow: ellipsis;
}

.office-station-label > span:last-child {
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.office-station-label i {
  width: 7px;
  height: 7px;
  flex: none;
  border-radius: 50%;
  background: var(--text-tertiary);
}

.office-station-label:not(:disabled) {
  cursor: pointer;
}

.office-station-label:not(:disabled):hover {
  border-color: var(--color-primary);
}

.office-station-label:disabled {
  color: var(--text-tertiary);
  cursor: default;
  opacity: 0.76;
}

.office-station-label.is-onlineIdle i {
  background: var(--status-success);
}

.office-station-label.is-busy i {
  background: var(--status-info);
}

.office-station-label.is-error i {
  background: var(--status-danger);
}

@media (max-height: 800px) {
  .office-scene {
    min-height: 470px;
  }

  .office-scene__labels {
    top: 22%;
  }
}
</style>
