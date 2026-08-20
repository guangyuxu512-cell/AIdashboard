<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

import type { DeviceOfficeAssetSource } from '../assets/device-office-assets'

defineProps<{
  source: DeviceOfficeAssetSource
  assetClass?: string
}>()

const video = ref<HTMLVideoElement | null>(null)

function syncVideoVisibility(): void {
  if (!video.value) return
  if (document.hidden) {
    video.value.pause()
  } else {
    void video.value.play().catch(() => undefined)
  }
}

onMounted(() =>
  document.addEventListener('visibilitychange', syncVideoVisibility),
)
onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', syncVideoVisibility)
  if (!video.value) return
  video.value.pause()
  video.value.removeAttribute('src')
  video.value.load()
})
</script>

<template>
  <img
    v-if="source.format === 'image'"
    :class="assetClass"
    :src="source.src"
    alt=""
    draggable="false"
  />
  <video
    v-else-if="source.format === 'transparent-webm'"
    ref="video"
    :class="assetClass"
    :src="source.src"
    :poster="source.poster"
    autoplay
    loop
    muted
    playsinline
  />
  <span
    v-else
    :class="assetClass"
    :data-pending-renderer="source.format"
    aria-hidden="true"
  />
</template>
