<script setup lang="ts">
import EmptyState from '@/shared/components/EmptyState.vue'

import type {
  GenerationExecutionResultView,
  InstantExecutionView,
} from '../model/types'
import InstantExecutionSummary from './InstantExecutionSummary.vue'
import InstantResultGrid from './InstantResultGrid.vue'

defineProps<{
  execution: InstantExecutionView | null
}>()

defineEmits<{
  downloadAll: []
  download: [result: GenerationExecutionResultView]
  save: [result: GenerationExecutionResultView]
  retry: [result: GenerationExecutionResultView]
}>()
</script>

<template>
  <section class="instant-result-viewer" data-testid="instant-result-viewer">
    <InstantExecutionSummary
      :execution="execution"
      @download-all="$emit('downloadAll')"
    />
    <div
      class="instant-result-viewer__scroll"
      data-testid="instant-result-scroll"
    >
      <InstantResultGrid
        v-if="execution"
        :results="execution.results"
        @download="$emit('download', $event)"
        @save="$emit('save', $event)"
        @retry="$emit('retry', $event)"
      />
      <EmptyState v-else description="暂无生成结果" />
    </div>
  </section>
</template>

<style scoped>
.instant-result-viewer {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}

.instant-result-viewer__scroll {
  min-width: 0;
  min-height: 0;
  flex: 1;
  padding: var(--space-4) var(--space-1) var(--space-1) 0;
  overflow-y: auto;
}
</style>
