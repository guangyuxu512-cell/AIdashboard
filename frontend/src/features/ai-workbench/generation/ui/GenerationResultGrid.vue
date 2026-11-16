<script setup lang="ts">
import { Download, RefreshCw } from '@lucide/vue'

import { AssetContentImage } from '@/entities/asset'
import EmptyState from '@/shared/components/EmptyState.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import { AppButton } from '@/shared/ui'

import {
  GENERATION_RESULT_STATUS_META,
  type GenerationResultView,
} from '../model/types'

withDefaults(
  defineProps<{
    results: GenerationResultView[]
    showRegenerate?: boolean
  }>(),
  {
    showRegenerate: true,
  },
)

defineEmits<{
  download: [result: GenerationResultView]
  regenerate: [result: GenerationResultView]
}>()
</script>

<template>
  <div
    v-if="results.length"
    class="generation-result-grid"
    data-testid="generation-result-grid"
  >
    <article
      v-for="result in results"
      :key="result.id"
      class="generation-result-card"
    >
      <AssetContentImage
        :src="result.thumbnailUrl ?? result.previewUrl"
        :alt="result.name"
      />
      <div class="generation-result-card__meta">
        <strong>{{ result.name }}</strong>
        <StatusTag
          :label="GENERATION_RESULT_STATUS_META[result.status].label"
          :tone="GENERATION_RESULT_STATUS_META[result.status].tone"
        />
      </div>
      <div class="generation-result-card__actions">
        <AppButton
          tone="text"
          aria-label="下载"
          @click="$emit('download', result)"
        >
          <Download :size="15" />
          下载
        </AppButton>
        <AppButton
          v-if="showRegenerate"
          tone="text"
          aria-label="再次生成"
          @click="$emit('regenerate', result)"
        >
          <RefreshCw :size="15" />
          再次生成
        </AppButton>
      </div>
    </article>
  </div>
  <EmptyState v-else description="暂无生成结果" />
</template>

<style scoped>
.generation-result-grid {
  display: grid;
  min-width: 0;
  gap: var(--layout-card-gap);
  grid-template-columns: repeat(auto-fill, minmax(var(--field-width-sm), 1fr));
}

.generation-result-card {
  min-width: 0;
  padding: var(--space-2);
  overflow: hidden;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  background: var(--bg-surface-solid);
}

.generation-result-card > :deep(.asset-content-image) {
  display: block;
  width: 100%;
  aspect-ratio: 1;
  border-radius: var(--radius-control);
  background: var(--bg-subtle);
}

.generation-result-card__meta,
.generation-result-card__actions {
  display: flex;
  min-width: 0;
  align-items: center;
}

.generation-result-card__meta {
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-1);
}

.generation-result-card__meta strong {
  overflow: hidden;
  font-size: var(--font-size-secondary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.generation-result-card__actions {
  flex-wrap: wrap;
  gap: var(--space-1);
  border-top: 1px solid var(--border-subtle);
  padding-top: var(--space-1);
}
</style>
