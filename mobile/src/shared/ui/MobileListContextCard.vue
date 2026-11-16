<script setup lang="ts">
defineProps<{
  label: string
  count: string | number
  contextLabel: string
  ariaLabel?: string
}>()
</script>

<template>
  <section
    class="mobile-list-context-card"
    :aria-label="ariaLabel || `${label} ${count}，${contextLabel}`"
    data-testid="mobile-list-context-card"
  >
    <span class="mobile-list-context-card__result">
      <strong>{{ label }}</strong>
      <span data-testid="task-context-count">{{ count }}</span>
    </span>
    <span
      class="mobile-list-context-card__context"
      data-testid="task-context-date"
    >
      {{ contextLabel }}
    </span>
  </section>
</template>

<style scoped>
.mobile-list-context-card {
  display: flex;
  width: 100%;
  min-width: 0;
  min-height: var(--visual-v2-list-context-height);
  padding: 0 var(--visual-v2-list-context-padding-x);
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  color: var(--visual-v2-page-text-primary);
  background: var(--visual-v2-list-context-background);
  border: var(--border-width) solid var(--visual-v2-list-context-border-color);
  border-radius: var(--visual-v2-list-context-radius);
  box-shadow: var(--visual-v2-list-context-shadow);
}

.mobile-list-context-card__result,
.mobile-list-context-card__context {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-list-context-card__result {
  display: inline-flex;
  gap: var(--space-2);
  align-items: baseline;
  font-size: var(--typography-v2-status-size);
  font-weight: var(--typography-v2-status-weight);
  line-height: var(--typography-v2-status-line-height);
}

.mobile-list-context-card__result strong {
  font: inherit;
}

.mobile-list-context-card__context {
  flex: none;
  color: var(--visual-v2-business-card-meta-color);
  font-size: var(--typography-v2-meta-size);
  font-weight: var(--typography-v2-meta-weight);
  line-height: var(--typography-v2-meta-line-height);
}
</style>
