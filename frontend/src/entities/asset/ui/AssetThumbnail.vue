<script setup lang="ts">
import { NImage } from 'naive-ui'

defineProps<{ src: string; alt: string }>()
</script>

<template>
  <NImage
    class="asset-thumbnail"
    :src="src"
    :alt="alt"
    width="56"
    height="40"
    object-fit="cover"
    preview-disabled
    lazy
  />
</template>

<style scoped>
.asset-thumbnail {
  display: block;
  overflow: hidden;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
}
</style>
