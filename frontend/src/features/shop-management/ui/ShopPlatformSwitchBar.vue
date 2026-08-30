<script setup lang="ts">
import {
  PLATFORM_ALL_NAV_ITEM,
  PLATFORM_NAVIGATION_ITEMS,
  PlatformIcon,
} from '@/entities/platform'
import type { ShopPlatformFilter } from '@/entities/shop'
import ContextSwitchBar from '@/shared/components/ContextSwitchBar.vue'

defineProps<{ modelValue: ShopPlatformFilter }>()

const emit = defineEmits<{
  'update:modelValue': [value: ShopPlatformFilter]
}>()

const navigationItems = [
  PLATFORM_ALL_NAV_ITEM,
  ...PLATFORM_NAVIGATION_ITEMS,
].map((item) => ({ key: item.code, label: item.label }))

function select(key: string): void {
  const item = navigationItems.find((candidate) => candidate.key === key)

  if (item) {
    emit('update:modelValue', item.key)
  }
}
</script>

<template>
  <ContextSwitchBar
    class="shop-platform-switch"
    label="店铺平台切换"
    :items="navigationItems"
    :active-key="modelValue"
    @select="select"
  >
    <template #icon="{ item }">
      <PlatformIcon :code="item.key as ShopPlatformFilter" />
    </template>
  </ContextSwitchBar>
</template>
