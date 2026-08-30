<script setup lang="ts">
import type { MaterialAssetReference } from '../model/types'
import EmptyState from '@/shared/components/EmptyState.vue'

const props = defineProps<{
  assets: readonly MaterialAssetReference[]
  selectedAssetId: string | null
  selectedAssetIds: readonly string[]
  selectionMode: boolean
}>()

const emit = defineEmits<{
  select: [assetId: string]
  'update:selected': [assetId: string, selected: boolean]
}>()

function isSelected(assetId: string): boolean {
  return props.selectedAssetIds.includes(assetId)
}

function activate(assetId: string): void {
  if (props.selectionMode) {
    emit('update:selected', assetId, !isSelected(assetId))
    return
  }
  emit('select', assetId)
}
</script>

<template>
  <EmptyState v-if="assets.length === 0" description="暂无素材" />
  <div v-else class="material-asset-grid" aria-label="素材列表">
    <button
      v-for="asset in assets"
      :key="asset.assetId"
      type="button"
      class="material-asset-card"
      :class="{
        'material-asset-card--active':
          !selectionMode && asset.assetId === selectedAssetId,
        'material-asset-card--selected': isSelected(asset.assetId),
      }"
      :aria-label="
        selectionMode ? `选择素材 ${asset.name}` : `查看素材 ${asset.name}`
      "
      :aria-pressed="selectionMode ? isSelected(asset.assetId) : undefined"
      :aria-current="
        !selectionMode && asset.assetId === selectedAssetId ? 'true' : undefined
      "
      :data-selected="isSelected(asset.assetId) ? 'true' : 'false'"
      @click="activate(asset.assetId)"
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
  position: relative;
  display: block;
  box-sizing: border-box;
  width: 100%;
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
    box-shadow 140ms ease;
}

.material-asset-card:hover {
  border-color: var(--border-strong);
  background: var(--bg-surface-hover);
}

.material-asset-card:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.material-asset-card--active {
  border-color: var(--border-strong);
  background: var(--bg-surface-hover);
}

.material-asset-card--selected,
.material-asset-card--selected:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
  box-shadow: inset 0 0 0 1px var(--color-primary);
}

.material-asset-card__preview {
  display: block;
  width: 100%;
  padding: 0;
  overflow: hidden;
  border: 0;
  border-radius: var(--radius-control);
  cursor: pointer;
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
