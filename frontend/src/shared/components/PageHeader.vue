<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

<template>
  <header class="page-header">
    <div class="page-header__copy">
      <h1>{{ title }}</h1>
      <p v-if="description">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="page-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<style scoped>
.page-header {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-5);
}

.page-header__copy {
  min-width: 0;
}

.page-header h1 {
  font-size: var(--font-size-page-title);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-compact);
}

.page-header p {
  margin-top: var(--space-1);
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.page-header__actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: var(--space-2);
}
</style>
