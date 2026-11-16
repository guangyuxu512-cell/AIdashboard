<script setup lang="ts">
import TableToolbar from '@/shared/components/TableToolbar.vue'

withDefaults(defineProps<{ label?: string }>(), {
  label: '管理工具栏',
})
</script>

<template>
  <section class="ai-management-toolbar" :aria-label="label">
    <TableToolbar class="ai-management-toolbar__layout">
      <slot />
      <template #actions>
        <slot name="actions" />
      </template>
    </TableToolbar>
  </section>
</template>

<style scoped>
.ai-management-toolbar {
  min-width: 0;
  padding: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  background: var(--bg-surface);
  box-shadow: var(--shadow-card);
}

.ai-management-toolbar__layout {
  min-width: 0;
  flex-wrap: wrap;
}

.ai-management-toolbar__layout :deep(.table-toolbar__leading),
.ai-management-toolbar__layout :deep(.table-toolbar__actions) {
  min-width: 0;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.ai-management-toolbar__layout :deep(.table-toolbar__leading) {
  flex: 1 1 var(--field-width-lg);
}

.ai-management-toolbar__layout :deep(.table-toolbar__actions) {
  flex: 0 0 auto;
  margin-left: auto;
}

@media (max-width: 900px) {
  .ai-management-toolbar__layout :deep(.table-toolbar__actions) {
    flex: 1 1 100%;
    justify-content: flex-end;
    margin-left: 0;
  }
}
</style>
