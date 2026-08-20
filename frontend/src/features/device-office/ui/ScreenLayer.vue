<script setup lang="ts">
import type { DeviceOfficeAssetSource } from '../assets/device-office-assets'
import type { DeviceVisualState } from '../model/types'
import OfficeAssetImage from './OfficeAssetImage.vue'

defineProps<{
  source: DeviceOfficeAssetSource
  visualState: Exclude<DeviceVisualState, 'empty'>
}>()
</script>

<template>
  <div
    class="station-layer screen-layer"
    :class="`is-${visualState}`"
    data-office-layer="03-screen-overlay"
  >
    <OfficeAssetImage :source="source" asset-class="screen-layer__asset" />
  </div>
</template>
