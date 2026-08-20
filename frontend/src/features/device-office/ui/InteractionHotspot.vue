<script setup lang="ts">
import type { OfficeRect } from '../model/office-layout'
import type { OfficeStationViewModel } from '../model/types'

defineProps<{
  station: OfficeStationViewModel
  rect: OfficeRect
}>()
defineEmits<{ select: [station: OfficeStationViewModel] }>()
</script>

<template>
  <button
    type="button"
    class="workstation-hotspot"
    :style="{
      left: `${rect.x}px`,
      top: `${rect.y}px`,
      width: `${rect.width}px`,
      height: `${rect.height}px`,
    }"
    :disabled="!station.device"
    :aria-label="
      station.device
        ? `查看设备 ${station.device.deviceName}`
        : `工位 ${station.slot} 空工位`
    "
    @click="station.device && $emit('select', station)"
  />
</template>
