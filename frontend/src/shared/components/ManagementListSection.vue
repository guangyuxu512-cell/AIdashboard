<script setup lang="ts">
import PageSection from './PageSection.vue'
</script>

<template>
  <PageSection class="management-list-section" fill>
    <div class="management-list-section__content">
      <slot />
    </div>
  </PageSection>
</template>

<style scoped>
.management-list-section__content {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: var(--space-4);
}
</style>
