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
    <span v-if="$slots.description || description" class="stat-card__description">
      <slot name="description">{{ description }}</slot>
    </span>
  </article>
</template>

<style scoped>
.stat-card {
  --stat-accent: var(--border-strong);

  position: relative;
  min-width: 0;
  overflow: hidden;
  padding: var(--space-3) var(--surface-padding);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  background: var(--bg-surface);
  box-shadow: var(--shadow-card);
  backdrop-filter: blur(var(--glass-blur));
}

.stat-card::before {
  position: absolute;
  top: var(--space-3);
  bottom: var(--space-3);
  left: 0;
  width: 2px;
  border-radius: 0 2px 2px 0;
  background: var(--stat-accent);
  content: '';
}

.stat-card__label,
.stat-card__description {
  display: block;
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.stat-card strong {
  display: block;
  margin-top: var(--space-1);
  font-size: var(--font-size-page-title);
  line-height: var(--line-height-compact);
}

.stat-card__description {
  margin-top: var(--space-1);
}

.stat-card--primary {
  --stat-accent: var(--color-primary);
}

.stat-card--success {
  --stat-accent: var(--status-success);
}

.stat-card--warning {
  --stat-accent: var(--status-warning);
}

.stat-card--error {
  --stat-accent: var(--status-danger);
}
</style>
