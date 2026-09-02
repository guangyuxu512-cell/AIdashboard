<script setup lang="ts">
import PageSection from '@/shared/components/PageSection.vue'

withDefaults(
  defineProps<{
    label?: string
    operationLabel?: string
    workspaceLabel?: string
  }>(),
  {
    label: 'AI 生图工作台',
    operationLabel: '生成设置',
    workspaceLabel: '生成结果',
  },
)
</script>

<template>
  <section class="ai-workbench-layout" :aria-label="label">
    <PageSection :aria-label="operationLabel" fill>
      <slot name="operation" />
    </PageSection>
    <PageSection :aria-label="workspaceLabel" fill>
      <slot name="workspace" />
    </PageSection>
  </section>
</template>

<style scoped>
.ai-workbench-layout {
  display: grid;
  min-width: 0;
  min-height: 0;
  flex: 1;
  align-items: stretch;
  gap: var(--layout-card-gap);
  grid-template-columns:
    minmax(var(--field-width-md), var(--field-width-xl))
    minmax(0, 1fr);
}

.ai-workbench-layout > :deep(.page-section) {
  overflow: hidden;
}

@media (max-width: 1100px) {
  .ai-workbench-layout {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
