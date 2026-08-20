<script setup lang="ts">
import type { ResolvedTheme } from '@/stores/theme'

import type { OfficeStationViewModel } from '../model/types'
import DeviceActorLayer from './DeviceActorLayer.vue'
import DeviceLabelLayer from './DeviceLabelLayer.vue'
import DeviceScreenOverlayLayer from './DeviceScreenOverlayLayer.vue'
import OfficeBackgroundLayer from './OfficeBackgroundLayer.vue'
import OfficeForegroundLayer from './OfficeForegroundLayer.vue'
import OfficeSlotsLayer from './OfficeSlotsLayer.vue'
import './office-stage.css'

defineProps<{
  stations: OfficeStationViewModel[]
  resolvedTheme: ResolvedTheme
}>()

defineEmits<{ select: [station: OfficeStationViewModel] }>()
</script>

<template>
  <section
    class="device-office-stage"
    :class="`device-office-stage--${resolvedTheme}`"
    aria-label="设备 2.5D 办公区"
    data-testid="device-office-stage"
  >
    <OfficeBackgroundLayer :resolved-theme="resolvedTheme" />
    <OfficeSlotsLayer :stations="stations" @select="$emit('select', $event)" />
    <DeviceActorLayer :stations="stations" />
    <DeviceScreenOverlayLayer :stations="stations" />
    <OfficeForegroundLayer :resolved-theme="resolvedTheme" />
    <DeviceLabelLayer :stations="stations" @select="$emit('select', $event)" />
  </section>
</template>
