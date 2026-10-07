<script setup lang="ts">
import { NImage } from 'naive-ui'
import { ref, watch } from 'vue'
import { AppButton } from '@/shared/ui'

const props = defineProps<{ src: string | null; title: string }>()
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
  <div class="product-image">
    <span v-if="!src">—</span>
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
        crossorigin: 'anonymous',
      }"
      @error="failed = true"
    />
  </div>
</template>

<style scoped>
.product-image {
  display: flex;
  justify-content: center;
  align-items: center;
  height: var(--control-height-default);
}
.product-image :deep(img) {
  width: var(--control-height-default);
  height: var(--control-height-default);
  object-fit: contain;
}
</style>
