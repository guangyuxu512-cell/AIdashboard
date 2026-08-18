<template>
  <section class="filter-bar" aria-label="筛选条件">
    <div class="filter-bar__fields">
      <slot />
    </div>
    <div
      v-if="$slots.actions || $slots['primary-action']"
      class="filter-bar__toolbar"
    >
      <div v-if="$slots.actions" class="filter-bar__actions">
        <slot name="actions" />
      </div>
      <div v-if="$slots['primary-action']" class="filter-bar__primary-action">
        <slot name="primary-action" />
      </div>
    </div>
  </section>
</template>

<style scoped>
.filter-bar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  background: var(--bg-surface);
}

.filter-bar__fields,
.filter-bar__toolbar,
.filter-bar__actions,
.filter-bar__primary-action {
  display: flex;
  align-items: center;
}

.filter-bar__fields {
  min-width: 0;
  flex: 1;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-3);
}

.filter-bar__toolbar {
  flex: 0 0 auto;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--space-4);
}

.filter-bar__actions,
.filter-bar__primary-action {
  gap: var(--space-2);
}
</style>
