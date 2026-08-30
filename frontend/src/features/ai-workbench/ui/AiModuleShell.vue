<script setup lang="ts">
import AiModuleNavigation from './AiModuleNavigation.vue'
</script>

<template>
  <div class="page-container ai-module-shell">
    <AiModuleNavigation />
    <div class="ai-module-shell__content">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.ai-module-shell {
  min-height: 100%;
}

.ai-module-shell__content {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: var(--layout-section-gap);
}
</style>
