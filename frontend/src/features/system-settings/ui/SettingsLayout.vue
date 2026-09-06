<script setup lang="ts">
import SettingsSideNav from './SettingsSideNav.vue'
</script>

<template>
  <section class="page-container settings-layout">
    <div class="settings-layout__surface">
      <aside class="settings-layout__navigation">
        <SettingsSideNav />
      </aside>
      <div class="settings-layout__content">
        <slot />
      </div>
    </div>
  </section>
</template>

<style scoped>
.settings-layout {
  height: 100%;
  min-height: 0;
}

.settings-layout__surface {
  display: grid;
  min-height: 0;
  flex: 1;
  grid-template-columns: minmax(156px, 184px) minmax(0, 1fr);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  background: var(--bg-surface);
  box-shadow: var(--shadow-card);
  backdrop-filter: blur(var(--glass-blur));
  overflow: hidden;
}

.settings-layout__navigation {
  min-width: 0;
  padding: var(--space-3);
  border-right: 1px solid var(--border-subtle);
  background: var(--bg-subtle);
}

.settings-layout__content {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  padding: var(--surface-padding);
  overflow: auto;
}

.settings-layout__content > :deep(*) {
  min-width: 0;
}

@media (max-width: 900px) {
  .settings-layout__surface {
    grid-template-columns: minmax(0, 1fr);
  }

  .settings-layout__navigation {
    padding: var(--space-2) var(--space-3);
    border-right: 0;
    border-bottom: 1px solid var(--border-subtle);
  }
}
</style>
