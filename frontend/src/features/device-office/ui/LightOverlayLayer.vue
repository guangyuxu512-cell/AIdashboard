<script setup lang="ts">
import type { DeviceOfficeAssetSource } from '../assets/device-office-assets'
import type { ResolvedTheme } from '@/stores/theme'
import OfficeAssetImage from './OfficeAssetImage.vue'

defineProps<{
  source: DeviceOfficeAssetSource
  theme: ResolvedTheme
}>()
</script>

<template>
  <div
    class="station-layer light-overlay-layer"
    :class="`is-${theme}`"
    data-office-layer="06-light-overlay"
  >
    <OfficeAssetImage
      :source="source"
      asset-class="light-overlay-layer__asset"
    />
  </div>
</template>
