<script setup lang="ts">
import type { DeviceOfficeAssetSource } from '../assets/device-office-assets'
import OfficeVisualAsset from './OfficeVisualAsset.vue'

defineProps<{ source: DeviceOfficeAssetSource | null }>()
</script>

<template>
  <div class="office-layer back-environment" aria-hidden="true">
    <OfficeVisualAsset
      v-if="source"
      :source="source"
      asset-class="back-environment__asset"
    />
  </div>
</template>
