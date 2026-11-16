<script setup lang="ts">
import { computed } from 'vue'
import { Download, Eye, Trash2, X } from '@lucide/vue'
import type { SelectOption } from 'naive-ui'

import {
  MATERIAL_ROLE_META,
  type MaterialAssetReference,
  type MaterialRole,
} from '../model/types'
import { assetPreviewTimeoutMs } from '@/entities/asset/api/asset-api'
import { AssetContentImage } from '@/entities/asset'
import { GENERATION_MODE_META } from '../../shared/model/generation-mode'
import StatusTag from '@/shared/components/StatusTag.vue'
import { AppButton, AppSelect } from '@/shared/ui'

const props = defineProps<{
  asset: MaterialAssetReference
  readOnly?: boolean
}>()

const emit = defineEmits<{
  close: []
  preview: [asset: MaterialAssetReference]
  download: [asset: MaterialAssetReference]
  remove: [asset: MaterialAssetReference]
  'update:role': [role: MaterialRole]
}>()

const roleOptions: SelectOption[] = [
  { label: MATERIAL_ROLE_META.PRODUCT_SOURCE.label, value: 'PRODUCT_SOURCE' },
  { label: MATERIAL_ROLE_META.STYLE_REFERENCE.label, value: 'STYLE_REFERENCE' },
]

const mediaTypeDisplay = computed(() => {
  if (props.asset.mediaType === 'image/jpeg') return 'JPEG'
  if (props.asset.mediaType === 'image/png') return 'PNG'
  if (props.asset.mediaType === 'image/webp') return 'WEBP'
  return props.asset.mediaType
})

const dimensionsDisplay = computed(() =>
  props.asset.width && props.asset.height
    ? `${props.asset.width} × ${props.asset.height}`
    : '—',
)

const sizeDisplay = computed(() => {
  const bytes = props.asset.sizeBytes
  if (bytes === undefined) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
})

const sourceDisplay = computed(() => {
  if (props.asset.sourceType === 'LOCAL_UPLOAD') return '本地上传'
  if (props.asset.sourceType === 'MATERIAL_IMPORT') return '素材导入'
  return GENERATION_MODE_META[props.asset.generationMode ?? 'NORMAL_GENERATION']
    .label
})

function updateRole(value: string | number | null): void {
  if (value === 'PRODUCT_SOURCE' || value === 'STYLE_REFERENCE') {
    emit('update:role', value)
  }
}
</script>

<template>
  <section class="material-asset-inspector" aria-label="素材详情">
    <div class="material-asset-inspector__header">
      <strong>素材详情</strong>
      <AppButton tone="text" aria-label="返回产品设置" @click="$emit('close')">
        <X :size="16" />
      </AppButton>
    </div>

    <div class="material-asset-inspector__preview">
      <AssetContentImage
        :src="asset.previewUrl"
        :fallback-src="asset.thumbnailUrl"
        :alt="asset.name"
        loading="eager"
        :timeout-ms="assetPreviewTimeoutMs"
        interactive
        @activate="$emit('preview', asset)"
      />
    </div>

    <strong class="material-asset-inspector__filename" :title="asset.name">
      {{ asset.name }}
    </strong>

    <dl class="material-asset-inspector__details">
      <div>
        <dt>类型</dt>
        <dd>
          <AppSelect
            v-if="asset.role !== 'AI_OUTPUT'"
            :model-value="asset.role"
            :disabled="readOnly"
            :options="roleOptions"
            aria-label="素材类型"
            @update:model-value="updateRole"
          />
          <StatusTag
            v-else
            :label="MATERIAL_ROLE_META[asset.role].label"
            tone="info"
          />
        </dd>
      </div>
      <div>
        <dt>格式</dt>
        <dd>{{ mediaTypeDisplay }}</dd>
      </div>
      <div>
        <dt>尺寸</dt>
        <dd>{{ dimensionsDisplay }}</dd>
      </div>
      <div>
        <dt>大小</dt>
        <dd>{{ sizeDisplay }}</dd>
      </div>
      <div>
        <dt>来源</dt>
        <dd>{{ sourceDisplay }}</dd>
      </div>
    </dl>

    <div class="material-asset-inspector__actions">
      <AppButton @click="$emit('preview', asset)">
        <Eye :size="16" />
        预览
      </AppButton>
      <AppButton
        :aria-label="`下载素材 ${asset.name}`"
        @click="$emit('download', asset)"
      >
        <Download :size="16" />
        下载
      </AppButton>
      <AppButton
        tone="danger"
        :disabled="readOnly"
        @click="$emit('remove', asset)"
      >
        <Trash2 :size="16" />
        删除
      </AppButton>
    </div>
  </section>
</template>

<style scoped>
.material-asset-inspector {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
}

.material-asset-inspector__header,
.material-asset-inspector__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.material-asset-inspector__header > strong {
  color: var(--text-primary);
  font-size: var(--font-size-section-title);
}

.material-asset-inspector__preview {
  display: grid;
  width: 100%;
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  background: var(--bg-subtle);
  aspect-ratio: 4 / 3;
}

.material-asset-inspector__preview :deep(.asset-content-image[role='button']) {
  cursor: zoom-in;
}

.material-asset-inspector__filename {
  overflow: hidden;
  color: var(--text-primary);
  font-weight: var(--font-weight-semibold);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.material-asset-inspector__details {
  display: flex;
  margin: 0;
  flex-direction: column;
  gap: var(--space-2);
}

.material-asset-inspector__details > div {
  display: grid;
  min-width: 0;
  min-height: var(--control-height-default);
  grid-template-columns: var(--field-width-xs) minmax(0, 1fr);
  align-items: center;
  gap: var(--space-2);
  border-bottom: 1px solid var(--border-subtle);
}

.material-asset-inspector__details dt {
  color: var(--text-tertiary);
}

.material-asset-inspector__details dd {
  min-width: 0;
  margin: 0;
  color: var(--text-secondary);
  text-align: right;
}

.material-asset-inspector__actions {
  justify-content: flex-end;
  margin-top: auto;
  padding-top: var(--space-2);
}
</style>
