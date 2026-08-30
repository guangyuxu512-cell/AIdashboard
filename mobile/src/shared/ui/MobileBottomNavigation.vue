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
  box-sizing: border-box;
  height: var(--visual-v2-bottom-nav-height);
  padding: var(--visual-v2-bottom-nav-padding-top)
    max(var(--visual-v2-bottom-nav-padding-x), var(--safe-area-right))
    var(--visual-v2-bottom-nav-padding-bottom)
    max(var(--visual-v2-bottom-nav-padding-x), var(--safe-area-left));
  background: var(--visual-v2-bottom-nav-background);
  border-top: var(--visual-v2-bottom-nav-border-width) solid
    var(--visual-v2-bottom-nav-border-color);
  box-shadow: var(--visual-v2-bottom-nav-shadow);
  backdrop-filter: blur(var(--visual-v2-bottom-nav-blur));
}

.mobile-bottom-navigation :deep(.van-tabbar-item) {
  flex: 1 1 20%;
  min-width: 0;
  padding-top: var(--visual-v2-bottom-nav-item-padding-top);
  justify-content: flex-start;
  color: var(--visual-v2-bottom-nav-inactive-color);
  font-size: var(--typography-v2-bottom-nav-size);
  font-weight: var(--typography-v2-bottom-nav-weight);
  line-height: var(--typography-v2-bottom-nav-line-height);
  white-space: nowrap;
}

.mobile-bottom-navigation :deep(.van-tabbar-item--active) {
  color: var(--visual-v2-bottom-nav-active-color);
}

.mobile-bottom-navigation :deep(.van-tabbar-item__icon) {
  width: var(--visual-v2-bottom-nav-icon-size);
  height: var(--visual-v2-bottom-nav-icon-size);
  margin-bottom: var(--visual-v2-bottom-nav-item-gap);
  font-size: var(--visual-v2-bottom-nav-icon-size);
}

.mobile-bottom-navigation :deep(.van-tabbar-item__icon .mobile-icon) {
  width: 100%;
  height: 100%;
  font-size: inherit;
}
</style>
