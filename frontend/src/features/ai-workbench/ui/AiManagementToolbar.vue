<script setup lang="ts">
import TableToolbar from '@/shared/components/TableToolbar.vue'

withDefaults(defineProps<{ label?: string }>(), {
  label: '管理工具栏',
})
</script>

<template>
  <section class="ai-management-toolbar" :aria-label="label">
    <TableToolbar class="ai-management-toolbar__layout">
      <div class="ai-management-toolbar__leading">
        <slot />
      </div>
      <template #actions>
        <div class="ai-management-toolbar__actions">
          <slot name="actions" />
        </div>
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

.ai-management-toolbar__layout,
.ai-management-toolbar__leading,
.ai-management-toolbar__actions {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--space-2);
}

.ai-management-toolbar__layout,
.ai-management-toolbar__leading,
.ai-management-toolbar__actions {
  flex-wrap: wrap;
}
</style>
