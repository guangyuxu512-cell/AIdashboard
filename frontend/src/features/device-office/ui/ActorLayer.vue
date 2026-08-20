<script setup lang="ts">
import type { DeviceOfficeAssetSource } from '../assets/device-office-assets'
import type { DeviceActorState } from '../model/types'
import OfficeAssetImage from './OfficeAssetImage.vue'

defineProps<{
  source: DeviceOfficeAssetSource
  actorState: DeviceActorState
}>()
</script>

<template>
  <div
    class="station-layer actor-layer"
    :class="`is-${actorState}`"
    data-office-layer="04-actor"
    :data-actor-state="actorState"
  >
    <OfficeAssetImage :source="source" asset-class="actor-layer__asset" />
  </div>
</template>
