<script setup lang="ts">
import type { ActorAssetProvider } from '../assets/device-office-assets'
import { getWorkstationSlot } from '../model/office-layout'
import type { OfficeStationViewModel } from '../model/types'
import MascotActor from './MascotActor.vue'

defineProps<{
  stations: OfficeStationViewModel[]
  provider: ActorAssetProvider
}>()
</script>

<template>
  <div class="office-layer device-actor-layer" aria-hidden="true">
    <MascotActor
      v-for="station in stations.filter(
        (item) => item.device && item.actorState && item.actorVariant,
      )"
      :key="station.slot"
      :actor-state="station.actorState!"
      :accent-variant="station.actorVariant!.accentVariant"
      :position="getWorkstationSlot(station.slot).actorAnchor"
      :scale="getWorkstationSlot(station.slot).actorScale"
      :z-index="getWorkstationSlot(station.slot).zIndex"
      :provider="provider"
    />
  </div>
</template>
