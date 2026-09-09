<script setup lang="ts">
import AssetContentImage from './AssetContentImage.vue'

defineProps<{ src: string; alt: string }>()
</script>

<template>
  <AssetContentImage
    class="asset-thumbnail"
    :src="src"
    :alt="alt"
  />
</template>

<style scoped>
.asset-thumbnail {
  display: block;
  width: 56px;
  height: 40px;
  overflow: hidden;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  object-fit: cover;
}
</style>
