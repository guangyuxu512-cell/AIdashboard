<script setup lang="ts">
import type { DeviceOfficeAssetSource } from '../assets/device-office-assets'
import type { OfficeRect } from '../model/office-layout'
import OfficeAssetImage from './OfficeAssetImage.vue'

defineProps<{
  source: DeviceOfficeAssetSource
  visualState: 'offline' | 'error'
  rect: OfficeRect
}>()
</script>

<template>
  <div
    class="fx-layer"
    :class="`is-${visualState}`"
    data-office-layer="07-fx-overlay"
  >
    <OfficeAssetImage
      :source="source"
      asset-class="fx-layer__asset"
      :style="{
        left: `${rect.x}px`,
        top: `${rect.y}px`,
        width: `${rect.width}px`,
        height: `${rect.height}px`,
      }"
    />
  </div>
</template>
