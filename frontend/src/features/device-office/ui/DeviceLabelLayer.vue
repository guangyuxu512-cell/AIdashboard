<script setup lang="ts">
import type { OfficePoint } from '../model/office-layout'
import type { OfficeStationViewModel } from '../model/types'

defineProps<{
  station: OfficeStationViewModel
  anchor: OfficePoint
}>()
defineEmits<{ select: [station: OfficeStationViewModel] }>()

const stateLabel = {
  empty: '空闲',
  onlineIdle: '在线',
  busy: '执行中',
  offline: '离线',
  error: '异常',
} as const
</script>

<template>
  <div
    class="device-label-layer"
    :style="{ left: `${anchor.x}px`, top: `${anchor.y}px` }"
    data-office-layer="08-label-ui"
  >
    <button
      v-if="station.device"
      type="button"
      class="device-label-pill"
      :class="`is-${station.visualState}`"
      :aria-label="`打开设备标签 ${station.device.deviceName}`"
      @click="$emit('select', station)"
    >
      <i aria-hidden="true" />
      <span>{{ station.device.deviceName }}</span>
      <small>{{ stateLabel[station.visualState] }}</small>
    </button>
    <span v-else class="device-label-pill is-empty" aria-hidden="true">
      <i />
      <span>工位 {{ station.slot }}</span>
      <small>{{ stateLabel.empty }}</small>
    </span>
  </div>
</template>
