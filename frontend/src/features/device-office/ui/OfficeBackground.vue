<script setup lang="ts">
import type { DeviceOfficeAssetSource } from '../assets/device-office-assets'
import OfficeVisualAsset from './OfficeVisualAsset.vue'

defineProps<{
  source: DeviceOfficeAssetSource | null
}>()
</script>

<template>
  <div class="office-layer office-background" aria-hidden="true">
    <OfficeVisualAsset
      v-if="source"
      :source="source"
      asset-class="office-background__asset"
    />
  </div>
</template>
