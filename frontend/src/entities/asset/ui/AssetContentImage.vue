<script setup lang="ts">
import { ref, watch } from 'vue'

import { fetchAssetContent } from '../api/asset-api'

const props = withDefaults(
  defineProps<{
    src: string
    alt: string
    loading?: 'eager' | 'lazy'
  }>(),
  { loading: 'lazy' },
)

const renderedSrc = ref('')

watch(
  () => props.src,
  (src, _previous, onCleanup) => {
    let objectUrl: string | null = null
    let disposed = false
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
  <img :src="renderedSrc" :alt="alt" :loading="loading" />
</template>
