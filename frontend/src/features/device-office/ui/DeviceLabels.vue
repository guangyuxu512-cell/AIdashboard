<script setup lang="ts">
import { getWorkstationSlot } from '../model/office-layout'
import type { OfficeStationViewModel } from '../model/types'

defineProps<{ stations: OfficeStationViewModel[] }>()
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
  <div class="office-layer device-labels">
    <div
      v-for="station in stations"
      :key="station.slot"
      class="device-label-anchor"
      :style="{
        left: `${getWorkstationSlot(station.slot).labelAnchor.x}px`,
        top: `${getWorkstationSlot(station.slot).labelAnchor.y}px`,
      }"
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
        <small>空闲</small>
      </span>
    </div>
  </div>
</template>
