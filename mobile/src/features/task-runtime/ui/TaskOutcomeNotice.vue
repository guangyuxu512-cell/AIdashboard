<script setup lang="ts">
import { NoticeBar as VanNoticeBar } from 'vant'
import { computed } from 'vue'

import type { TaskStatusDto } from '@/entities/task'

import { getTaskResultSummary } from '../model/runtime-display'

const props = defineProps<{
  status: TaskStatusDto
  result: Record<string, unknown> | null
  errorMessage: string | null
  errorCode: string | null
}>()

const failed = computed(
  () => props.status === 'failed' || props.status === 'lost',
)
</script>

<template>
  <VanNoticeBar
    v-if="status === 'success'"
    class="mobile-notice-bar--success"
    :text="getTaskResultSummary(result)"
    wrapable
    data-testid="task-result"
  />
  <VanNoticeBar
    v-else-if="failed"
    class="mobile-notice-bar--danger"
    wrapable
    data-testid="task-error-message"
  >
    <div class="task-outcome__error">
      <span>{{ errorMessage || '任务未能完成' }}</span>
      <code v-if="errorCode">{{ errorCode }}</code>
    </div>
  </VanNoticeBar>
</template>

<style scoped>
.task-outcome__error {
  display: grid;
  min-width: 0;
  gap: var(--space-1);
  white-space: normal;
}

.task-outcome__error code {
  min-width: 0;
  overflow-wrap: anywhere;
  font-family: var(--font-family-mono);
  font-size: var(--font-size-caption);
  white-space: normal;
}
</style>
