<script setup lang="ts">
import { ref, watch } from 'vue'
import { NImage } from 'naive-ui'

import { fetchAssetContent } from '../api/asset-api'

const props = defineProps<{ src: string; alt: string }>()
const renderedSrc = ref('')

watch(
  () => props.src,
  (src, _previous, onCleanup) => {
    let disposed = false
    let objectUrl: string | null = null
    const controller = new AbortController()
    renderedSrc.value = ''

    onCleanup(() => {
      disposed = true
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    })

    if (!src || /^(?:blob|data):/i.test(src)) {
      renderedSrc.value = src
      return
    }

    void fetchAssetContent(src, controller.signal)
      .then((blob) => {
        if (disposed) return
        objectUrl = URL.createObjectURL(blob)
        renderedSrc.value = objectUrl
      })
      .catch(() => {
        if (!disposed) renderedSrc.value = ''
      })
  },
  { immediate: true },
)
</script>

<template>
  <NImage
    class="asset-thumbnail"
    :src="renderedSrc"
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
