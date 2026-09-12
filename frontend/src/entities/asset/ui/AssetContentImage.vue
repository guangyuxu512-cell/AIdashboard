<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

import { fetchAssetContent } from '../api/asset-api'

const props = withDefaults(
  defineProps<{
    src: string
    alt: string
    loading?: 'eager' | 'lazy'
  }>(),
  { loading: 'lazy' },
)

const target = ref<HTMLElement | null>(null)
const renderedSrc = ref('')
const state = ref<'empty' | 'idle' | 'loading' | 'ready' | 'error'>('empty')
const retryLoader = ref<(() => void) | null>(null)

function isDirectImageSource(value: string): boolean {
  return /^(?:blob|data):/i.test(value)
}

function retry(): void {
  retryLoader.value?.()
}

function handleImageError(): void {
  renderedSrc.value = ''
  state.value = 'error'
}

watch(
  [() => props.src, () => props.loading],
  ([src, loading], _previous, onCleanup) => {
    let objectUrl: string | null = null
    let disposed = false
    let requestInFlight = false
    let observer: IntersectionObserver | null = null
    const controller = new AbortController()
    renderedSrc.value = ''
    retryLoader.value = null
    state.value = src ? 'idle' : 'empty'

    onCleanup(() => {
      disposed = true
      controller.abort()
      observer?.disconnect()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    })

    if (!src) {
      renderedSrc.value = src
      state.value = 'empty'
      return
    }

    if (isDirectImageSource(src)) {
      renderedSrc.value = src
      state.value = 'ready'
      return
    }

    const load = () => {
      if (disposed || requestInFlight) return
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl)
        objectUrl = null
      }
      requestInFlight = true
      state.value = 'loading'
      void fetchAssetContent(src, controller.signal)
        .then((blob) => {
          if (disposed) return
          objectUrl = URL.createObjectURL(blob)
          renderedSrc.value = objectUrl
          state.value = 'ready'
        })
        .catch(() => {
          if (disposed) return
          renderedSrc.value = ''
          state.value = 'error'
        })
        .finally(() => {
          requestInFlight = false
        })
    }
    retryLoader.value = load

    if (loading === 'lazy' && typeof IntersectionObserver !== 'undefined') {
      state.value = 'idle'
      const observeImage = () => {
        if (disposed || observer) return
        const imageTarget = target.value
        if (!imageTarget) return
        observer = new IntersectionObserver((entries) => {
          if (!entries.some((entry) => entry.isIntersecting)) return
          observer?.disconnect()
          observer = null
          load()
        })
        observer.observe(imageTarget)
      }
      if (target.value) observeImage()
      else void nextTick().then(observeImage)
      return
    }
    load()
  },
  { immediate: true, flush: 'post' },
)
</script>

<template>
  <div ref="target" class="asset-content-image" :data-state="state">
    <img
      v-if="renderedSrc"
      class="asset-content-image__image"
      :src="renderedSrc"
      :alt="alt"
      :loading="loading"
      @error="handleImageError"
    />
    <button
      v-else-if="state === 'error'"
      class="asset-content-image__retry"
      type="button"
      :aria-label="`重新加载图片：${alt}`"
      @click="retry"
    >
      重试
    </button>
    <span
      v-else-if="state !== 'empty'"
      class="asset-content-image__placeholder"
      aria-hidden="true"
    />
  </div>
</template>

<style scoped>
.asset-content-image {
  display: grid;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  place-items: center;
  background: var(--bg-subtle);
}

.asset-content-image__image,
.asset-content-image__placeholder,
.asset-content-image__retry {
  display: block;
  width: 100%;
  height: 100%;
}

.asset-content-image__image {
  object-fit: inherit;
}

.asset-content-image__placeholder {
  background: var(--bg-muted);
}

.asset-content-image__retry {
  border: 0;
  color: var(--text-secondary);
  font: inherit;
  font-size: var(--font-size-secondary);
  cursor: pointer;
  background: var(--bg-muted);
}
</style>
