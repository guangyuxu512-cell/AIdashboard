<script setup lang="ts">
import {
  Cell as VanCell,
  CellGroup as VanCellGroup,
  Popup as VanPopup,
} from 'vant'

import {
  formatDeviceDateTime,
  type Device,
  type DeviceProviderInventoryReadDto,
  type DeviceSkillCapabilityReadDto,
} from '@/entities/device'
import { MobileIcon } from '@/shared/icons'

import DeviceProviderDetails from './DeviceProviderDetails.vue'
import DeviceSkillDetails from './DeviceSkillDetails.vue'

defineProps<{
  show: boolean
  device: Device
  inventories: DeviceProviderInventoryReadDto[] | undefined
  capabilities: DeviceSkillCapabilityReadDto[] | undefined
}>()

const emit = defineEmits<{
  'update:show': [show: boolean]
}>()
</script>

<template>
  <VanPopup
    class="device-more-sheet"
    :show="show"
    position="bottom"
    round
    close-on-popstate
    data-testid="device-more-sheet"
    @update:show="emit('update:show', $event)"
  >
    <div class="device-more-sheet__handle" aria-hidden="true" />
    <div class="device-more-sheet__header">
      <h2>更多信息</h2>
      <button
        type="button"
        class="device-more-sheet__close mobile-icon-button mobile-pressable"
        aria-label="关闭更多信息"
        @click="emit('update:show', false)"
      >
        <MobileIcon name="close" />
      </button>
    </div>

    <div class="device-more-sheet__content mobile-scroll-container">
      <section aria-label="设备技术信息">
        <h3>设备</h3>
        <VanCellGroup>
          <VanCell title="设备 ID" :value="device.deviceId" />
          <VanCell
            title="启用状态"
            :value="device.enabled ? '已启用' : '已停用'"
          />
          <VanCell title="位置" :value="device.location || '—'" />
          <VanCell title="备注" :value="device.note || '—'" />
          <VanCell
            title="更新时间"
            :value="formatDeviceDateTime(device.updatedAt)"
          />
        </VanCellGroup>
      </section>

      <section v-if="device.workerRuntime" aria-label="运行端技术信息">
        <h3>运行端</h3>
        <VanCellGroup>
          <VanCell
            title="Worker版本"
            :value="device.workerRuntime.workerVersion || '—'"
          />
          <VanCell
            title="启动时间"
            :value="formatDeviceDateTime(device.workerRuntime.startedAt)"
          />
          <VanCell
            title="更新时间"
            :value="formatDeviceDateTime(device.workerRuntime.updatedAt)"
          />
        </VanCellGroup>
      </section>

      <DeviceProviderDetails
        v-if="inventories !== undefined"
        :inventories="inventories"
      />
      <DeviceSkillDetails
        v-if="capabilities !== undefined"
        :capabilities="capabilities"
      />
    </div>
  </VanPopup>
</template>

<style scoped>
.device-more-sheet {
  display: grid;
  width: min(100%, var(--layout-content-max-width));
  max-height: var(--overlay-height-max);
  margin-inline: auto;
  overflow: hidden;
  color: var(--text-primary);
  background: var(--visual-v2-detail-sheet-background);
}

.device-more-sheet__handle {
  width: var(--visual-v2-detail-sheet-handle-width);
  height: var(--visual-v2-detail-sheet-handle-height);
  margin: var(--visual-v2-detail-sheet-handle-margin-top) auto 0;
  background: var(--visual-v2-detail-sheet-handle-color);
  border-radius: var(--radius-round);
}

.device-more-sheet__header {
  display: grid;
  min-width: 0;
  padding: var(--visual-v2-detail-sheet-padding-top)
    max(var(--visual-v2-detail-sheet-padding-x), var(--safe-area-right)) 0
    max(var(--visual-v2-detail-sheet-padding-x), var(--safe-area-left));
  grid-template-columns: minmax(0, 1fr) var(--touch-target-min);
  align-items: center;
}

.device-more-sheet__header h2 {
  overflow: hidden;
  font-size: var(--typography-v2-detail-section-title-size);
  font-weight: var(--typography-v2-detail-section-title-weight);
  line-height: var(--typography-v2-detail-section-title-line-height);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-more-sheet__content {
  display: grid;
  min-width: 0;
  min-height: 0;
  gap: var(--visual-v2-detail-section-gap);
  padding: var(--visual-v2-detail-sheet-title-gap)
    max(var(--visual-v2-detail-sheet-padding-x), var(--safe-area-right))
    max(var(--visual-v2-detail-sheet-padding-bottom), var(--safe-area-bottom))
    max(var(--visual-v2-detail-sheet-padding-x), var(--safe-area-left));
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior-y: contain;
}

.device-more-sheet__content section {
  display: grid;
  min-width: 0;
  gap: var(--space-3);
}

.device-more-sheet__content h3 {
  font-size: var(--font-size-label);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-label);
}
</style>
