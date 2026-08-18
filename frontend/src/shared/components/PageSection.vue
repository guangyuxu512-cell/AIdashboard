<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string
    description?: string
    surface?: 'card' | 'transparent'
  }>(),
  {
    title: undefined,
    description: undefined,
    surface: 'card',
  },
)
</script>

<template>
  <section class="page-section" :class="`page-section--${surface}`">
    <header
      v-if="title || description || $slots.actions"
      class="page-section__header"
    >
      <div>
        <h2 v-if="title">{{ title }}</h2>
        <p v-if="description">{{ description }}</p>
      </div>
      <div v-if="$slots.actions" class="page-section__actions">
        <slot name="actions" />
      </div>
    </header>
    <div class="page-section__content">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.page-section {
  min-width: 0;
}

.page-section--card {
  padding: var(--surface-padding);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  background: var(--bg-surface);
  box-shadow: var(--shadow-card);
  backdrop-filter: blur(var(--glass-blur));
}

.page-section__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-3);
}

.page-section__header h2 {
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-compact);
}

.page-section__header p {
  margin-top: var(--space-1);
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.page-section__actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.page-section__content {
  min-width: 0;
}
</style>
