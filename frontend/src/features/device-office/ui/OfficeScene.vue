<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDocumentVisibility } from '@vueuse/core'
import { TresCanvas } from '@tresjs/core'

import type { ResolvedTheme } from '@/stores/theme'

import type { OfficeStationViewModel } from '../model/types'
import { getOfficeSceneTheme } from '../theme/office-scene-theme'
import OfficeWorld from './OfficeWorld.vue'

const props = defineProps<{
  stations: OfficeStationViewModel[]
  resolvedTheme: ResolvedTheme
}>()

const emit = defineEmits<{ select: [station: OfficeStationViewModel] }>()
const documentVisibility = useDocumentVisibility()
const theme = computed(() => getOfficeSceneTheme(props.resolvedTheme))
const clearColor = computed(() => theme.value.wall)
const renderedFps = ref(0)

const stateLabel = {
  empty: '空工位',
  onlineIdle: '在线',
  busy: '执行中',
  offline: '离线',
  error: '异常',
} as const
</script>

<template>
  <section
    class="office-scene"
    :class="`office-scene--${resolvedTheme}`"
    aria-label="设备 3D 办公区"
    data-testid="device-office-scene"
    :data-render-fps="renderedFps"
  >
    <TresCanvas
      v-if="documentVisibility === 'visible'"
      class="office-scene__canvas"
      :clear-color="clearColor"
      :dpr="[1, 1.5]"
      :shadows="true"
      render-mode="always"
      :alpha="false"
      :antialias="true"
    >
      <OfficeWorld
        :stations="stations"
        :theme="theme"
        @select="emit('select', $event)"
        @performance="renderedFps = $event"
      />
    </TresCanvas>
    <div v-else class="office-scene__paused">页面处于后台，3D 渲染已暂停</div>

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
        <span class="office-station-label__name">
          {{ station.device?.deviceName ?? `工位 ${station.slot}` }}
        </span>
        <span class="office-station-label__status">
          <i aria-hidden="true" />{{ stateLabel[station.visualState] }}
        </span>
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

.office-scene__canvas {
  position: absolute !important;
  inset: 0;
}

.office-scene__paused {
  display: grid;
  height: 100%;
  place-items: center;
  color: var(--text-secondary);
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
  align-self: end;
  min-width: 0;
  max-width: var(--field-width-sm);
  padding: var(--space-1) var(--space-2);
  border: 1px solid color-mix(in srgb, var(--border-strong) 72%, transparent);
  border-radius: var(--radius-control);
  background: color-mix(in srgb, var(--bg-surface-solid) 88%, transparent);
  box-shadow: var(--shadow-card);
  color: var(--text-primary);
  font: inherit;
  text-align: left;
  backdrop-filter: blur(var(--glass-blur));
  pointer-events: auto;
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

.office-station-label__name,
.office-station-label__status {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.office-station-label__name {
  font-weight: var(--font-weight-medium);
}

.office-station-label__status {
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.office-station-label__status i {
  display: inline-block;
  width: 7px;
  height: 7px;
  margin-right: var(--space-1);
  border-radius: 50%;
  background: var(--text-tertiary);
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
