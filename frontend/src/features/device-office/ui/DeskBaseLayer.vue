<script setup lang="ts">
import type { DeviceOfficeAssetSource } from '../assets/device-office-assets'
import OfficeAssetImage from './OfficeAssetImage.vue'

defineProps<{ source: DeviceOfficeAssetSource }>()
</script>

<template>
  <div class="station-layer desk-base-layer" data-office-layer="02-desk-base">
    <OfficeAssetImage :source="source" eager />
  </div>
</template>
