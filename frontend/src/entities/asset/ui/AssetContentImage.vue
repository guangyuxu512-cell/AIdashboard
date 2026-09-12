<script setup lang="ts">
import { NSpin } from 'naive-ui'
import { nextTick, ref, watch } from 'vue'

import { fetchAssetContent } from '../api/asset-api'

const props = withDefaults(
  defineProps<{
    src: string
    alt: string
    fallbackSrc?: string
    loading?: 'eager' | 'lazy'
    timeoutMs?: number
    interactive?: boolean
  }>(),
  {
    fallbackSrc: undefined,
    loading: 'lazy',
    timeoutMs: undefined,
    interactive: false,
  },
)

const emit = defineEmits<{
  activate: []
}>()

const target = ref<HTMLElement | null>(null)
const renderedSrc = ref('')
const fallbackRenderedSrc = ref('')
const state = ref<'empty' | 'idle' | 'loading' | 'ready' | 'error'>('empty')
const retryLoader = ref<(() => void) | null>(null)

function isDirectImageSource(value: string): boolean {
  return /^(?:blob|data):/i.test(value)
}

function retry(): void {
  retryLoader.value?.()
}

function activate(): void {
  if (props.interactive && state.value !== 'error') emit('activate')
}

function handleImageError(): void {
  renderedSrc.value = ''
  fallbackRenderedSrc.value = ''
  state.value = 'error'
}

watch(
  [
    () => props.src,
    () => props.fallbackSrc,
    () => props.loading,
    () => props.timeoutMs,
  ],
  ([src, fallbackSrc, loading, timeoutMs], _previous, onCleanup) => {
    let objectUrl: string | null = null
    let fallbackObjectUrl: string | null = null
    let disposed = false
    let requestInFlight = false
    let observer: IntersectionObserver | null = null
    const controller = new AbortController()
    renderedSrc.value = ''
    fallbackRenderedSrc.value = ''
    retryLoader.value = null
    state.value = src ? 'idle' : 'empty'

    const releaseFallback = () => {
      if (fallbackObjectUrl) URL.revokeObjectURL(fallbackObjectUrl)
      fallbackObjectUrl = null
      fallbackRenderedSrc.value = ''
    }

    onCleanup(() => {
      disposed = true
      controller.abort()
      observer?.disconnect()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
      if (fallbackObjectUrl) URL.revokeObjectURL(fallbackObjectUrl)
    })

    if (!src) {
      renderedSrc.value = src
      state.value = 'empty'
      return
    }

    const loadFallback = () => {
      if (!fallbackSrc || fallbackSrc === src) return
      releaseFallback()
      if (isDirectImageSource(fallbackSrc)) {
        fallbackRenderedSrc.value = fallbackSrc
        return
      }
      void fetchAssetContent(fallbackSrc, controller.signal)
        .then((blob) => {
          if (disposed || state.value !== 'loading') return
          fallbackObjectUrl = URL.createObjectURL(blob)
          fallbackRenderedSrc.value = fallbackObjectUrl
        })
        .catch(() => {
          // The full image request stays authoritative. A failed thumbnail must
          // not hide its explicit loading or error state.
        })
    }

    if (isDirectImageSource(src)) {
      renderedSrc.value = src
      state.value = 'ready'
      return
    }

    const load = () => {
      if (disposed || requestInFlight) return
      loadFallback()
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl)
        objectUrl = null
      }
      requestInFlight = true
      state.value = 'loading'
      const request =
        timeoutMs === undefined
          ? fetchAssetContent(src, controller.signal)
          : fetchAssetContent(src, controller.signal, { timeoutMs })
      void request
        .then((blob) => {
          if (disposed) return
          releaseFallback()
          objectUrl = URL.createObjectURL(blob)
          renderedSrc.value = objectUrl
          state.value = 'ready'
        })
        .catch(() => {
          if (disposed) return
          releaseFallback()
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
  <div
    ref="target"
    class="asset-content-image"
    :data-state="state"
    :data-source="
      renderedSrc ? 'content' : fallbackRenderedSrc ? 'thumbnail' : 'none'
    "
    :role="interactive && state !== 'error' ? 'button' : undefined"
    :tabindex="interactive && state !== 'error' ? 0 : undefined"
    :aria-label="interactive && state !== 'error' ? `预览 ${alt}` : undefined"
    @click="activate"
    @keydown.enter="activate"
    @keydown.space.prevent="activate"
  >
    <img
      v-if="renderedSrc || fallbackRenderedSrc"
      class="asset-content-image__image"
      :src="renderedSrc || fallbackRenderedSrc"
      :alt="alt"
      :loading="loading"
      @error="handleImageError"
    />
    <span
      v-if="state === 'loading' && fallbackRenderedSrc"
      class="asset-content-image__loading"
      role="status"
    >
      <NSpin size="small" />
      <span>正在加载原图</span>
    </span>
    <button
      v-else-if="state === 'error'"
      class="asset-content-image__retry"
      type="button"
      :aria-label="`重新加载图片：${alt}`"
      @click.stop="retry"
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
  position: relative;
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

.asset-content-image[role='button'] {
  cursor: pointer;
}

.asset-content-image__placeholder {
  background: var(--bg-muted);
}

.asset-content-image__loading {
  position: absolute;
  right: var(--space-2);
  bottom: var(--space-2);
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
  pointer-events: none;
  background: var(--bg-surface-solid);
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
