<script setup lang="ts">
import {
  PLATFORM_ALL_NAV_ITEM,
  PLATFORM_NAVIGATION_ITEMS,
  PlatformIcon,
} from '@/entities/platform'
import type { ShopPlatformFilter } from '@/entities/shop'
import AppButton from '@/shared/ui/AppButton.vue'

defineProps<{ modelValue: ShopPlatformFilter }>()

defineEmits<{ 'update:modelValue': [value: ShopPlatformFilter] }>()

const navigationItems = [
  PLATFORM_ALL_NAV_ITEM,
  ...PLATFORM_NAVIGATION_ITEMS,
]
</script>

<template>
  <nav class="shop-platform-switch" aria-label="店铺平台切换">
    <AppButton
      v-for="item in navigationItems"
      :key="item.code"
      :tone="modelValue === item.code ? 'secondary' : 'text'"
      :class="{
        'shop-platform-switch__item--active': modelValue === item.code,
      }"
      :aria-pressed="modelValue === item.code"
      :aria-label="item.label"
      @click="$emit('update:modelValue', item.code)"
    >
      <span class="shop-platform-switch__content">
        <PlatformIcon :code="item.code" />
        <span>{{ item.label }}</span>
      </span>
    </AppButton>
  </nav>
</template>

<style scoped>
.shop-platform-switch {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2);
  overflow-x: auto;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  background: var(--bg-surface);
}

.shop-platform-switch__content {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

.shop-platform-switch__item--active {
  color: var(--accent-primary);
}
</style>
