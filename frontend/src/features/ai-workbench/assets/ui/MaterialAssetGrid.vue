<script setup lang="ts">
import type { MaterialAssetReference } from '../model/types'
import EmptyState from '@/shared/components/EmptyState.vue'

defineProps<{
  assets: readonly MaterialAssetReference[]
  selectedAssetId: string | null
}>()

defineEmits<{
  select: [assetId: string]
}>()
</script>

<template>
  <EmptyState v-if="assets.length === 0" description="暂无素材" />
  <div v-else class="material-asset-grid" aria-label="素材列表">
    <button
      v-for="asset in assets"
      :key="asset.assetId"
      class="material-asset-card"
      :class="{
        'material-asset-card--selected': asset.assetId === selectedAssetId,
      }"
      type="button"
      :aria-label="`查看素材 ${asset.name}`"
      :aria-pressed="asset.assetId === selectedAssetId"
      @click="$emit('select', asset.assetId)"
    >
      <span class="material-asset-card__preview">
        <img :src="asset.previewUrl" :alt="asset.name" loading="lazy" />
      </span>
      <span class="material-asset-card__name" :title="asset.name">
        {{ asset.name }}
      </span>
    </button>
  </div>
</template>

<style scoped>
.material-asset-grid {
  display: grid;
  min-width: 0;
  align-content: start;
  gap: var(--layout-card-gap);
  grid-template-columns: repeat(auto-fill, minmax(var(--field-width-xs), 1fr));
}

.material-asset-card {
  min-width: 0;
  padding: var(--space-1);
  overflow: hidden;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  color: var(--text-primary);
  font: inherit;
  text-align: left;
  cursor: pointer;
  background: var(--bg-surface-solid);
  transition:
    border-color 140ms ease,
    background-color 140ms ease,
    transform 140ms ease;
}

.material-asset-card:hover {
  border-color: var(--border-strong);
  background: var(--bg-surface-hover);
  transform: translateY(-1px);
}

.material-asset-card--selected {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px var(--color-primary-soft);
}

.material-asset-card__preview {
  display: block;
  overflow: hidden;
  border-radius: var(--radius-control);
  background: var(--bg-subtle);
  aspect-ratio: 1;
}

.material-asset-card__preview img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.material-asset-card__name {
  display: block;
  padding: var(--space-2) var(--space-1) var(--space-1);
  overflow: hidden;
  font-size: var(--font-size-secondary);
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
