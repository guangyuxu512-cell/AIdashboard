<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string
    value: string | number
    description?: string
    tone?: 'neutral' | 'primary' | 'success' | 'warning' | 'error'
  }>(),
  {
    description: undefined,
    tone: 'neutral',
  },
)
</script>

<template>
  <article class="stat-card" :class="`stat-card--${tone}`">
    <span class="stat-card__label">{{ label }}</span>
    <strong>{{ value }}</strong>
    <span v-if="description" class="stat-card__description">{{ description }}</span>
  </article>
</template>

<style scoped>
.stat-card {
  min-width: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border-default);
  border-radius: var(--radius-card);
  background: var(--color-bg-card);
  box-shadow: var(--shadow-card);
}

.stat-card__label,
.stat-card__description {
  display: block;
  color: var(--color-text-secondary);
  font-size: var(--font-size-secondary);
}

.stat-card strong {
  display: block;
  margin-top: var(--space-2);
  font-size: var(--font-size-page-title);
  line-height: var(--line-height-compact);
}

.stat-card__description {
  margin-top: var(--space-2);
}

.stat-card--primary {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}

.stat-card--success {
  border-color: var(--color-success);
  background: var(--color-success-soft);
}

.stat-card--warning {
  border-color: var(--color-warning);
  background: var(--color-warning-soft);
}

.stat-card--error {
  border-color: var(--color-error);
  background: var(--color-error-soft);
}
</style>
