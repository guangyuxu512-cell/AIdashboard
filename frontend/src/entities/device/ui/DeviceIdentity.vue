<script setup lang="ts">
import { Monitor } from '@lucide/vue'

defineProps<{ name: string }>()
</script>

<template>
  <span class="device-identity">
    <Monitor
      class="device-identity__icon"
      :size="18"
      :stroke-width="1.8"
      aria-hidden="true"
      data-testid="device-monitor-icon"
    />
    <span class="device-identity__name">{{ name }}</span>
  </span>
</template>

<style scoped>
.device-identity {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: var(--space-2);
}

.device-identity__icon {
  flex: 0 0 auto;
  color: var(--text-link);
}

.device-identity__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
