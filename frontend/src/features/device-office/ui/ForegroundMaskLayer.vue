<script setup lang="ts">
import type { DeviceOfficeAssetSource } from '../assets/device-office-assets'
import OfficeAssetImage from './OfficeAssetImage.vue'

defineProps<{ source: DeviceOfficeAssetSource }>()
</script>

<template>
  <div
    class="station-layer foreground-mask-layer"
    data-office-layer="05-foreground-mask"
  >
    <OfficeAssetImage :source="source" eager />
  </div>
</template>
