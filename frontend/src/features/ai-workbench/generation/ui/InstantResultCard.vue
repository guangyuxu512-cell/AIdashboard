<script setup lang="ts">
import {
  CircleAlert,
  Clock3,
  Download,
  Image as ImageIcon,
  MoreHorizontal,
  RotateCcw,
} from '@lucide/vue'
import { NDropdown, NSpin } from 'naive-ui'
import type { DropdownOption } from 'naive-ui'
import { computed } from 'vue'

import { AssetContentImage } from '@/entities/asset'
import StatusTag from '@/shared/components/StatusTag.vue'
import { AppButton } from '@/shared/ui'

import {
  GENERATION_EXECUTION_RESULT_STATUS_META,
  type GenerationExecutionResultView,
} from '../model/types'

const props = withDefaults(
  defineProps<{
    result: GenerationExecutionResultView
    showActions?: boolean
    showAssetLibraryStatus?: boolean
  }>(),
  {
    showActions: true,
    showAssetLibraryStatus: false,
  },
)

const emit = defineEmits<{
  download: [result: GenerationExecutionResultView]
  save: [result: GenerationExecutionResultView]
  retry: [result: GenerationExecutionResultView]
}>()

const resultLabel = computed(
  () => props.result.name ?? `生成结果 ${props.result.slotIndex + 1}`,
)

const moreOptions: DropdownOption[] = [
  { key: 'save-to-assets', label: '保存到素材库' },
]

function selectMoreAction(key: string | number): void {
  if (key === 'save-to-assets') emit('save', props.result)
}
</script>

<template>
  <article
    class="instant-result-card"
    data-testid="instant-result-card"
    :data-result-id="result.id"
    :data-slot-index="result.slotIndex"
    :data-result-status="result.status"
  >
    <div class="instant-result-card__preview">
      <AssetContentImage
        v-if="result.status === 'SUCCESS' && result.previewUrl"
        class="instant-result-card__image"
        :src="result.previewUrl"
        :alt="resultLabel"
      />
      <ImageIcon
        v-else-if="result.status === 'SUCCESS'"
        :size="24"
        aria-hidden="true"
      />
      <div
        v-else-if="result.status === 'RUNNING'"
        class="instant-result-card__state"
      >
        <NSpin size="medium" />
        <span>生成中</span>
      </div>
      <div
        v-else-if="result.status === 'WAITING'"
        class="instant-result-card__state"
      >
        <Clock3 :size="22" aria-hidden="true" />
        <span>等待中</span>
      </div>
      <div v-else class="instant-result-card__state">
        <CircleAlert :size="22" aria-hidden="true" />
        <span>{{ result.errorMessage ?? '生成失败' }}</span>
      </div>
    </div>

    <div class="instant-result-card__meta">
      <strong :title="resultLabel">{{ resultLabel }}</strong>
      <StatusTag
        :label="GENERATION_EXECUTION_RESULT_STATUS_META[result.status].label"
        :tone="GENERATION_EXECUTION_RESULT_STATUS_META[result.status].tone"
      />
    </div>

    <footer class="instant-result-card__actions">
      <template v-if="showActions && result.status === 'SUCCESS'">
        <AppButton
          tone="text"
          :aria-label="`下载 ${resultLabel}`"
          @click="$emit('download', result)"
        >
          <Download :size="14" />
          下载
        </AppButton>
        <NDropdown
          v-if="!result.savedToProductId"
          trigger="click"
          :options="moreOptions"
          @select="selectMoreAction"
        >
          <AppButton tone="text" :aria-label="`更多操作 ${resultLabel}`">
            <MoreHorizontal :size="16" />
          </AppButton>
        </NDropdown>
      </template>
      <AppButton
        v-else-if="showActions && result.status === 'FAILED'"
        tone="text"
        :aria-label="`重试 ${resultLabel}`"
        @click="$emit('retry', result)"
      >
        <RotateCcw :size="14" />
        重试
      </AppButton>
      <span
        v-if="
          result.status === 'SUCCESS' &&
          (showAssetLibraryStatus || result.savedToProductId)
        "
        class="instant-result-card__asset-status"
      >
        {{ result.savedToProductId ? '已加入素材库' : '未加入素材库' }}
      </span>
    </footer>
  </article>
</template>

<style scoped>
.instant-result-card {
  display: flex;
  min-width: 0;
  overflow: hidden;
  flex-direction: column;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  background: var(--bg-surface-solid);
}

.instant-result-card__preview {
  display: grid;
  width: 100%;
  aspect-ratio: 1;
  overflow: hidden;
  place-items: center;
  color: var(--text-tertiary);
  background: var(--bg-subtle);
}

.instant-result-card__image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.instant-result-card__state {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: var(--space-2);
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.instant-result-card__meta,
.instant-result-card__actions {
  display: flex;
  min-width: 0;
  align-items: center;
}

.instant-result-card__meta {
  min-height: var(--control-height-large);
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3) var(--space-1);
}

.instant-result-card__meta strong {
  min-width: 0;
  overflow: hidden;
  font-size: var(--font-size-secondary);
  font-weight: var(--font-weight-medium);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.instant-result-card__actions {
  min-height: var(--control-height-large);
  gap: var(--space-1);
  padding: 0 var(--space-2) var(--space-1);
  border-top: 1px solid var(--border-subtle);
}

.instant-result-card__asset-status {
  margin-left: auto;
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
  white-space: nowrap;
}
</style>
