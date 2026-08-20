<script setup lang="ts">
import type { DeviceOfficeAssetSource } from '../assets/device-office-assets'

defineProps<{
  source: DeviceOfficeAssetSource
  assetClass?: string
  eager?: boolean
}>()
</script>

<template>
  <img
    :class="['office-asset-image', assetClass]"
    :src="source.src"
    alt=""
    :loading="eager ? 'eager' : 'lazy'"
    decoding="async"
    draggable="false"
  />
</template>
