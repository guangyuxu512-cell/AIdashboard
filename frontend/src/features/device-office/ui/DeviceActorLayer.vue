<script setup lang="ts">
import { officeActorAssets } from '../assets/office-2d-asset-manifest'
import type { OfficeStationViewModel } from '../model/types'

defineProps<{ stations: OfficeStationViewModel[] }>()
</script>

<template>
  <div
    class="office-stage-layer office-stage-grid device-actor-layer"
    aria-hidden="true"
  >
    <div
      v-for="station in stations"
      :key="station.slot"
      class="device-actor-slot"
      :data-behavior="station.localBehavior ?? undefined"
    >
      <img
        v-if="station.device && station.visualState !== 'empty'"
        class="device-actor-slot__asset"
        :class="`is-${station.visualState}`"
        :src="officeActorAssets[station.visualState]"
        alt=""
        draggable="false"
      />
    </div>
  </div>
</template>
