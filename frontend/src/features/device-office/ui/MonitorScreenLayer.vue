<script setup lang="ts">
import type { DeviceOfficeAssetManifest } from '../assets/device-office-assets'
import { getWorkstationSlot } from '../model/office-layout'
import type { OfficeStationViewModel } from '../model/types'
import MonitorScreen from './MonitorScreen.vue'

defineProps<{
  stations: OfficeStationViewModel[]
  manifest: DeviceOfficeAssetManifest
}>()
</script>

<template>
  <div class="office-layer monitor-screen-layer" aria-hidden="true">
    <MonitorScreen
      v-for="station in stations"
      :key="station.slot"
      :visual-state="station.visualState"
      :rect="getWorkstationSlot(station.slot).screenRect"
      :source="manifest.screens[station.visualState]"
    />
  </div>
</template>
