<script setup lang="ts">
import { NImage, NText } from 'naive-ui'
import { ref, watch } from 'vue'
import { AppButton } from '@/shared/ui'

const props = withDefaults(
  defineProps<{
    src: string | null
    title: string
    size?: 'thumbnail' | 'summary'
  }>(),
  { size: 'summary' },
)
const failed = ref(false)
const revision = ref(0)
watch(
  () => props.src,
  () => {
    failed.value = false
  },
)
function retry() {
  failed.value = false
  revision.value += 1
}
</script>

<template>
  <div class="product-image" :class="`product-image--${size}`">
    <NText v-if="!src" :depth="3">—</NText>
    <AppButton
      v-else-if="failed"
      tone="text"
      aria-label="重试商品图片"
      @click="retry"
      >重试</AppButton
    >
    <NImage
      v-else
      :key="revision"
      :src="src"
      :alt="title"
      object-fit="contain"
      :img-props="{
        loading: 'lazy',
        referrerpolicy: 'no-referrer',
      }"
      @error="failed = true"
    />
  </div>
</template>

<style scoped>
.product-image {
  --product-image-size: 80px;
  display: flex;
  justify-content: center;
  align-items: center;
  height: var(--product-image-size);
}
.product-image--thumbnail {
  --product-image-size: 56px;
}
.product-image :deep(img) {
  width: var(--product-image-size);
  height: var(--product-image-size);
  object-fit: contain;
}
</style>
