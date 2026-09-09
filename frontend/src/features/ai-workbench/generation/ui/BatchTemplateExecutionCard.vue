<script setup lang="ts">
import {
  CircleAlert,
  Clock3,
  Download,
  Image as ImageIcon,
  RotateCcw,
} from '@lucide/vue'
import { NSpin } from 'naive-ui'
import { computed } from 'vue'

import { AssetContentImage } from '@/entities/asset'
import StatusTag from '@/shared/components/StatusTag.vue'
import { AppButton } from '@/shared/ui'

import type { BatchTemplateExecutionIdentity } from '../model/batch-execution'
import {
  BATCH_EXECUTION_STATUS_META,
  type BatchTemplateExecutionView,
} from '../model/types'

const props = defineProps<{
  productId: string
  templateGroupId: string
  template: BatchTemplateExecutionView
}>()

const emit = defineEmits<{
  download: [template: BatchTemplateExecutionView]
  retry: [identity: BatchTemplateExecutionIdentity]
}>()

const successCount = computed(
  () =>
    props.template.results.filter((result) => result.status === 'SUCCESS')
      .length,
)
const failedCount = computed(
  () =>
    props.template.results.filter((result) => result.status === 'FAILED')
      .length,
)

function retry(): void {
  emit('retry', {
    productId: props.productId,
    templateGroupId: props.templateGroupId,
    templateId: props.template.templateId,
  })
}
</script>

<template>
  <article
    class="batch-template-execution-card"
    data-testid="batch-template-execution-card"
    :data-template-id="template.templateId"
    :data-template-status="template.status"
  >
    <header class="batch-template-execution-card__header">
      <strong :title="template.templateName">{{
        template.templateName
      }}</strong>
      <StatusTag
        :label="BATCH_EXECUTION_STATUS_META[template.status].label"
        :tone="BATCH_EXECUTION_STATUS_META[template.status].tone"
      />
    </header>

    <div
      class="batch-template-execution-card__results"
      :aria-label="`${template.templateName} 结果`"
    >
      <div
        v-for="(result, index) in template.results"
        :key="result.id"
        class="batch-template-result"
        data-testid="batch-result-thumbnail"
        :data-result-status="result.status"
        :aria-label="`${template.templateName} 结果 ${index + 1} ${result.status}`"
      >
        <AssetContentImage
          v-if="result.status === 'SUCCESS' && result.previewUrl"
          class="batch-template-result__preview"
          :src="result.thumbnailUrl ?? result.previewUrl"
          :alt="`${template.templateName} 结果 ${index + 1}`"
        />
        <ImageIcon
          v-else-if="result.status === 'SUCCESS'"
          :size="16"
          aria-hidden="true"
        />
        <NSpin v-else-if="result.status === 'RUNNING'" size="small" />
        <Clock3
          v-else-if="result.status === 'WAITING'"
          :size="16"
          aria-hidden="true"
        />
        <CircleAlert v-else :size="16" aria-hidden="true" />
      </div>
    </div>

    <footer class="batch-template-execution-card__footer">
      <span class="batch-template-execution-card__meta">
        <span>{{ template.completedCount }} / {{ template.totalCount }}</span>
        <span v-if="successCount" data-testid="batch-archived-count">
          已归档 {{ successCount }}
        </span>
      </span>
      <span class="batch-template-execution-card__actions">
        <AppButton
          v-if="failedCount"
          tone="text"
          :aria-label="`重试 ${template.templateName}`"
          @click="retry"
        >
          <RotateCcw :size="14" />
          重试
        </AppButton>
        <AppButton
          v-if="successCount"
          tone="text"
          :aria-label="`下载 ${template.templateName}`"
          @click="$emit('download', template)"
        >
          <Download :size="14" />
          下载
        </AppButton>
      </span>
    </footer>
  </article>
</template>

<style scoped>
.batch-template-execution-card {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  background: var(--bg-surface-solid);
}

.batch-template-execution-card__header,
.batch-template-execution-card__footer,
.batch-template-execution-card__meta,
.batch-template-execution-card__actions,
.batch-template-execution-card__results {
  display: flex;
  min-width: 0;
  align-items: center;
}

.batch-template-execution-card__header,
.batch-template-execution-card__footer {
  justify-content: space-between;
  gap: var(--space-3);
}

.batch-template-execution-card__header strong {
  min-width: 0;
  overflow: hidden;
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.batch-template-execution-card__results,
.batch-template-execution-card__meta,
.batch-template-execution-card__actions {
  gap: var(--space-2);
}

.batch-template-execution-card__results {
  flex-wrap: wrap;
}

.batch-template-result {
  display: grid;
  width: calc(var(--control-height-large) + var(--space-2));
  aspect-ratio: 1;
  overflow: hidden;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  place-items: center;
  color: var(--text-tertiary);
  background: var(--bg-subtle);
}

.batch-template-result[data-result-status='FAILED'] {
  color: var(--status-danger);
}

.batch-template-result__preview {
  width: 100%;
  height: 100%;
}

.batch-template-execution-card__meta {
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
  font-variant-numeric: tabular-nums;
}
</style>
