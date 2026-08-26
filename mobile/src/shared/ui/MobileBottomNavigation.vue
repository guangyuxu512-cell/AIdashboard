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
}>()
</script>

<template>
  <VanTabbar
    class="mobile-bottom-navigation"
    data-testid="mobile-bottom-navigation"
    route
    :fixed="false"
    :border="false"
    :safe-area-inset-bottom="false"
  >
    <VanTabbarItem
      v-for="item in items"
      :key="item.key"
      :to="item.to"
      :icon="item.icon"
    >
      {{ item.label }}
    </VanTabbarItem>
  </VanTabbar>
</template>

<style scoped>
.mobile-bottom-navigation {
  border-top: var(--border-width) solid var(--border-subtle);
}
</style>
