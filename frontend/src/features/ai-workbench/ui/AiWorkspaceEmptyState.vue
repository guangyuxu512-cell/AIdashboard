<script setup lang="ts">
import EmptyState from '@/shared/components/EmptyState.vue'

defineProps<{
  title: string
}>()
</script>

<template>
  <section class="ai-workspace-empty-state" :aria-label="title">
    <EmptyState :description="title" />
  </section>
</template>

<style scoped>
.ai-workspace-empty-state {
  display: grid;
  min-width: 0;
  min-height: 0;
  flex: 1;
  place-items: center;
  padding: var(--space-8) var(--space-5);
  border: 1px dashed var(--border-default);
  border-radius: var(--radius-card);
  background: var(--bg-subtle);
}
</style>
