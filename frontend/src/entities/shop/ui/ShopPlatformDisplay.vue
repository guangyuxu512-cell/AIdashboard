<script setup lang="ts">
import { computed } from 'vue'

import { SHOP_PLATFORM_META } from '../model/status-meta'
import type { ShopPlatform } from '../model/types'

const props = withDefaults(
  defineProps<{ platform: ShopPlatform; label?: boolean }>(),
  { label: true },
)

const meta = computed(() => SHOP_PLATFORM_META[props.platform])
</script>

<template>
  <span class="shop-platform-display">
    <img
      class="shop-platform-display__icon"
      :src="meta.icon"
      :alt="meta.iconAlt"
    />
    <span v-if="label">{{ meta.label }}</span>
  </span>
</template>

<style scoped>
.shop-platform-display {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: var(--space-2);
  white-space: nowrap;
}

.shop-platform-display__icon {
  width: var(--space-5);
  height: var(--space-5);
  flex: 0 0 auto;
  border-radius: var(--radius-sm);
}
</style>
