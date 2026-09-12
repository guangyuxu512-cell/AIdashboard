<script setup lang="ts">
import {
  ChevronLeft,
  ChevronRight,
  Download,
  ZoomIn,
  ZoomOut,
} from '@lucide/vue'
import { computed, ref, watch } from 'vue'

import type { AssetPreviewSource } from '../model/preview'
import { AppButton, AppDialog } from '@/shared/ui'

import AssetContentImage from './AssetContentImage.vue'

const props = withDefaults(
  defineProps<{
    show: boolean
    items: readonly AssetPreviewSource[]
    selectedAssetId?: string | null
  }>(),
  { selectedAssetId: null },
)

const emit = defineEmits<{
  'update:show': [value: boolean]
  download: [asset: AssetPreviewSource]
}>()

const activeAssetId = ref<string | null>(null)
const zoom = ref(1)
const zoomSteps = [1, 1.25, 1.5, 2] as const

const activeIndex = computed(() => {
  const index = props.items.findIndex((item) => item.id === activeAssetId.value)
  return index >= 0 ? index : 0
})
const activeAsset = computed(() => props.items[activeIndex.value] ?? null)
const hasPrevious = computed(() => activeIndex.value > 0)
const hasNext = computed(() => activeIndex.value < props.items.length - 1)
const canZoomOut = computed(() => zoom.value > zoomSteps[0]!)
const canZoomIn = computed(() => zoom.value < zoomSteps[zoomSteps.length - 1]!)
const imageStyle = computed(() => ({ transform: `scale(${zoom.value})` }))

function syncActiveAsset(): void {
  const requested = props.selectedAssetId
  activeAssetId.value = props.items.some((item) => item.id === requested)
    ? requested
    : (props.items[0]?.id ?? null)
  zoom.value = 1
}

watch(
  [() => props.show, () => props.selectedAssetId, () => props.items],
  ([show]) => {
    if (show) syncActiveAsset()
  },
  { immediate: true, deep: true },
)

function move(offset: -1 | 1): void {
  const item = props.items[activeIndex.value + offset]
  if (!item) return
  activeAssetId.value = item.id
  zoom.value = 1
}

function adjustZoom(offset: -1 | 1): void {
  const index = zoomSteps.findIndex((value) => value === zoom.value)
  const next = zoomSteps[index + offset]
  if (next !== undefined) zoom.value = next
}
</script>

<template>
  <AppDialog
    :show="show"
    :title="activeAsset?.name ?? '图片预览'"
    size="lg"
    positive-text="关闭"
    :show-negative="false"
    @update:show="emit('update:show', $event)"
    @confirm="emit('update:show', false)"
  >
    <section class="asset-preview-dialog" aria-label="图片预览">
      <div class="asset-preview-dialog__canvas">
        <AssetContentImage
          v-if="activeAsset"
          class="asset-preview-dialog__image"
          :style="imageStyle"
          :src="activeAsset.contentUrl"
          :alt="activeAsset.name"
          loading="eager"
        />
      </div>
      <p v-if="activeAsset" class="asset-preview-dialog__caption">
        {{ activeIndex + 1 }} / {{ items.length }} · {{ activeAsset.name }}
      </p>
    </section>
    <template #footer-start>
      <div class="asset-preview-dialog__controls">
        <AppButton
          tone="text"
          :disabled="!hasPrevious"
          aria-label="查看上一张图片"
          @click="move(-1)"
        >
          <ChevronLeft :size="16" />
          上一张
        </AppButton>
        <AppButton
          tone="text"
          :disabled="!hasNext"
          aria-label="查看下一张图片"
          @click="move(1)"
        >
          下一张
          <ChevronRight :size="16" />
        </AppButton>
        <AppButton
          tone="text"
          :disabled="!canZoomOut"
          aria-label="缩小预览"
          @click="adjustZoom(-1)"
        >
          <ZoomOut :size="16" />
        </AppButton>
        <AppButton
          tone="text"
          :disabled="!canZoomIn"
          aria-label="放大预览"
          @click="adjustZoom(1)"
        >
          <ZoomIn :size="16" />
        </AppButton>
        <AppButton
          v-if="activeAsset"
          tone="text"
          :aria-label="`下载 ${activeAsset.name}`"
          @click="emit('download', activeAsset)"
        >
          <Download :size="16" />
          下载
        </AppButton>
      </div>
    </template>
  </AppDialog>
</template>

<style scoped>
.asset-preview-dialog {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-2);
}

.asset-preview-dialog__canvas {
  display: grid;
  min-width: 0;
  height: min(calc(var(--dialog-max-height) - var(--field-width-lg)), 68vh);
  min-height: var(--field-width-md);
  overflow: auto;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  place-items: center;
  background: var(--bg-subtle);
}

.asset-preview-dialog__image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  transform-origin: center;
  transition: transform 140ms ease;
}

.asset-preview-dialog__caption {
  min-width: 0;
  margin: 0;
  overflow: hidden;
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.asset-preview-dialog__controls {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  gap: var(--space-1);
}
</style>
