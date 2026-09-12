<script setup lang="ts">
import type { GenerationExecutionResultView } from '../model/types'
import InstantResultCard from './InstantResultCard.vue'

withDefaults(
  defineProps<{
    results: readonly GenerationExecutionResultView[]
    showActions?: boolean
  }>(),
  {
    showActions: true,
  },
)

defineEmits<{
  download: [result: GenerationExecutionResultView]
  retry: [result: GenerationExecutionResultView]
  preview: [result: GenerationExecutionResultView]
}>()
</script>

<template>
  <div class="instant-result-grid" data-testid="instant-result-grid">
    <InstantResultCard
      v-for="result in results"
      :key="result.id"
      :result="result"
      :show-actions="showActions"
      @download="$emit('download', $event)"
      @retry="$emit('retry', $event)"
      @preview="$emit('preview', $event)"
    />
  </div>
</template>

<style scoped>
.instant-result-grid {
  display: grid;
  min-width: 0;
  align-items: start;
  gap: var(--layout-card-gap);
  grid-template-columns: repeat(
    auto-fill,
    minmax(min(100%, var(--field-width-sm)), 1fr)
  );
}
</style>
