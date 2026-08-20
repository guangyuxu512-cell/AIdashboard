<script setup lang="ts">
import type { DeviceOfficeAssetSource } from '../assets/device-office-assets'
import OfficeVisualAsset from './OfficeVisualAsset.vue'

defineProps<{ source: DeviceOfficeAssetSource | null }>()
</script>

<template>
  <div class="office-layer foreground-occlusion" aria-hidden="true">
    <OfficeVisualAsset
      v-if="source"
      :source="source"
      asset-class="foreground-occlusion__asset"
    />
  </div>
</template>
