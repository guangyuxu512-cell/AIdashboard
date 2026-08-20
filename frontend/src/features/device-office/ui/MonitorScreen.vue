<script setup lang="ts">
import type { DeviceOfficeAssetSource } from '../assets/device-office-assets'
import type { OfficeRect } from '../model/office-layout'
import type { DeviceVisualState } from '../model/types'
import OfficeVisualAsset from './OfficeVisualAsset.vue'

defineProps<{
  visualState: DeviceVisualState
  rect: OfficeRect
  source: DeviceOfficeAssetSource | null
}>()
</script>

<template>
  <div
    class="monitor-screen"
    :style="{
      left: `${rect.x}px`,
      top: `${rect.y}px`,
      width: `${rect.width}px`,
      height: `${rect.height}px`,
    }"
    :data-screen-state="visualState"
    :data-asset-status="source ? 'ready' : 'missing'"
    aria-hidden="true"
  >
    <OfficeVisualAsset
      v-if="source"
      :source="source"
      asset-class="monitor-screen__asset"
    />
  </div>
</template>
