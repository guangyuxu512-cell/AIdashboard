<script setup lang="ts">
import { Tabbar as VanTabbar, TabbarItem as VanTabbarItem } from 'vant'
import type { RouteLocationRaw } from 'vue-router'

import { MobileIcon, type MobileIconName } from '@/shared/icons'

interface MobileNavigationItem {
  key: string
  label: string
  icon: MobileIconName
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
      :data-testid="`mobile-bottom-navigation-${item.key}`"
      :to="item.to"
    >
      <template #icon>
        <MobileIcon :name="item.icon" />
      </template>
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
  flex: 1 1 20%;
  min-width: 0;
  color: var(--text-tertiary);
  white-space: nowrap;
}

.mobile-bottom-navigation :deep(.van-tabbar-item--active) {
  color: var(--text-selected);
}
</style>
