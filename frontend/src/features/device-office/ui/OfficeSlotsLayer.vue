<script setup lang="ts">
import type { OfficeStationViewModel } from '../model/types'

defineProps<{ stations: OfficeStationViewModel[] }>()
defineEmits<{ select: [station: OfficeStationViewModel] }>()
</script>

<template>
  <div class="office-stage-layer office-stage-grid office-slots-layer">
    <button
      v-for="station in stations"
      :key="station.slot"
      type="button"
      class="office-workstation"
      :class="`is-${station.visualState}`"
      :data-testid="`office-slot-${station.slot}`"
      :disabled="!station.device"
      :aria-label="
        station.device
          ? `查看设备 ${station.device.deviceName}`
          : `工位 ${station.slot} 空工位`
      "
      @click="station.device && $emit('select', station)"
    >
      <span class="office-workstation__desk" aria-hidden="true">
        <span class="office-workstation__monitor" />
        <span class="office-workstation__keyboard" />
        <span class="office-workstation__plant" />
      </span>
      <span class="office-workstation__chair" aria-hidden="true" />
    </button>
  </div>
</template>
