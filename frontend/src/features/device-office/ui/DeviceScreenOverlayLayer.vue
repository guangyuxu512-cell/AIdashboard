<script setup lang="ts">
import { officeScreenAssets } from '../assets/office-2d-asset-manifest'
import type { OfficeStationViewModel } from '../model/types'

defineProps<{ stations: OfficeStationViewModel[] }>()
</script>

<template>
  <div
    class="office-stage-layer office-stage-grid device-screen-layer"
    aria-hidden="true"
  >
    <div v-for="station in stations" :key="station.slot" class="device-screen-slot">
      <img
        class="device-screen-slot__asset"
        :class="`is-${station.visualState}`"
        :src="officeScreenAssets[station.visualState]"
        alt=""
        draggable="false"
      />
    </div>
  </div>
</template>
