<script setup lang="ts">
import type { DeviceOfficeAssetSource } from '../assets/device-office-assets'
import OfficeAssetImage from './OfficeAssetImage.vue'

defineProps<{ source: DeviceOfficeAssetSource }>()
</script>

<template>
  <div class="office-background-layer" data-office-layer="01-background">
    <OfficeAssetImage :source="source" eager />
  </div>
</template>
