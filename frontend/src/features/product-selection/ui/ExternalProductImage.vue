<script setup lang="ts">
import { ProductImage } from '@/entities/product'

// Compatibility facade: existing detail callers and dimensions stay intact.
withDefaults(
  defineProps<{
    src: string | null
    title: string
    size?: 'thumbnail' | 'summary'
  }>(),
  { size: 'summary' },
)
</script>

<template>
  <ProductImage :src="src" :title="title" :size="size" />
</template>
