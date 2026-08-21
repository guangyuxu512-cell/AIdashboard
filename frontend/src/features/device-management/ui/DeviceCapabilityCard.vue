<script setup lang="ts">
defineProps<{ title: string; description?: string }>()
</script>

<template>
  <article class="capability-card">
    <header class="capability-card__header">
      <div>
        <h4>{{ title }}</h4>
        <p v-if="description">{{ description }}</p>
      </div>
      <slot name="status" />
    </header>
    <div class="capability-card__content">
      <slot />
    </div>
    <footer v-if="$slots.actions" class="capability-card__actions">
      <slot name="actions" />
    </footer>
  </article>
</template>

<style scoped>
.capability-card {
  padding: var(--space-4);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  background: var(--bg-subtle);
}

.capability-card__header,
.capability-card__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.capability-card__header h4 {
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-semibold);
}

.capability-card__header p {
  margin-top: var(--space-1);
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.capability-card__content {
  margin-top: var(--space-4);
}

.capability-card__actions {
  justify-content: flex-end;
  margin-top: var(--space-4);
}
</style>
