<template>
  <section class="filter-bar" aria-label="筛选条件">
    <div class="filter-bar__fields">
      <slot />
    </div>
    <div v-if="$slots.actions" class="filter-bar__actions">
      <slot name="actions" />
    </div>
  </section>
</template>

<style scoped>
.filter-bar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4);
  border: 1px solid var(--color-border-default);
  border-radius: var(--radius-card);
  background: var(--color-bg-subtle);
}

.filter-bar__fields,
.filter-bar__actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.filter-bar__fields {
  min-width: 0;
  flex: 1;
  flex-wrap: wrap;
}

.filter-bar__actions {
  flex: 0 0 auto;
}
</style>
