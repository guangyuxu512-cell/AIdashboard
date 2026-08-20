<script setup lang="ts">
import { getWorkstationSlot } from '../model/office-layout'
import type { OfficeStationViewModel } from '../model/types'

defineProps<{
  stations: OfficeStationViewModel[]
  referencePreview: boolean
}>()
defineEmits<{ select: [station: OfficeStationViewModel] }>()
</script>

<template>
  <div
    class="office-layer interaction-hotspots"
    :class="{ 'is-calibrating': referencePreview }"
  >
    <button
      v-for="station in stations"
      :key="station.slot"
      type="button"
      class="workstation-hotspot"
      :style="{
        left: `${getWorkstationSlot(station.slot).hotspot.x}px`,
        top: `${getWorkstationSlot(station.slot).hotspot.y}px`,
        width: `${getWorkstationSlot(station.slot).hotspot.width}px`,
        height: `${getWorkstationSlot(station.slot).hotspot.height}px`,
        zIndex: getWorkstationSlot(station.slot).zIndex,
      }"
      :data-testid="`office-slot-${station.slot}`"
      :data-slot-id="station.slot"
      :disabled="!station.device"
      :aria-label="
        station.device
          ? `查看设备 ${station.device.deviceName}`
          : `工位 ${station.slot} 空工位`
      "
      @click="station.device && $emit('select', station)"
    >
      <span v-if="referencePreview" aria-hidden="true"
        >S{{ station.slot }}</span
      >
    </button>
  </div>
</template>
