<script setup lang="ts">
import { Tabbar as VanTabbar, TabbarItem as VanTabbarItem } from 'vant'
import type { RouteLocationRaw } from 'vue-router'

interface MobileNavigationItem {
  key: string
  label: string
  icon: string
  to: RouteLocationRaw
}

defineProps<{
  items: readonly MobileNavigationItem[]
  activeKey?: string
}>()
</script>

<template>
  <VanTabbar
    class="mobile-bottom-navigation"
    data-testid="mobile-bottom-navigation"
    :model-value="activeKey"
    :fixed="false"
    :border="false"
    :safe-area-inset-bottom="false"
  >
    <VanTabbarItem
      v-for="item in items"
      :key="item.key"
      :name="item.key"
      class="mobile-pressable mobile-pressable--control"
      :to="item.to"
      :icon="item.icon"
    >
      {{ item.label }}
    </VanTabbarItem>
  </VanTabbar>
</template>

<style scoped>
.mobile-bottom-navigation {
  background: var(--bg-surface-raised);
  border-top: var(--border-width) solid var(--border-subtle);
  box-shadow: var(--shadow-tabbar);
}

.mobile-bottom-navigation :deep(.van-tabbar-item) {
  color: var(--text-tertiary);
}

.mobile-bottom-navigation :deep(.van-tabbar-item--active) {
  color: var(--text-selected);
}
</style>
