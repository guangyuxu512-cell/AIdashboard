<script setup lang="ts">
import { SHOP_PLATFORM_NAV_ITEMS, type ShopPlatformFilter } from '@/entities/shop'
import AppButton from '@/shared/ui/AppButton.vue'

defineProps<{ modelValue: ShopPlatformFilter }>()

defineEmits<{ 'update:modelValue': [value: ShopPlatformFilter] }>()
</script>

<template>
  <nav class="shop-platform-switch" aria-label="店铺平台切换">
    <AppButton
      v-for="item in SHOP_PLATFORM_NAV_ITEMS"
      :key="item.value"
      :tone="modelValue === item.value ? 'secondary' : 'text'"
      :class="{
        'shop-platform-switch__item--active': modelValue === item.value,
      }"
      :aria-pressed="modelValue === item.value"
      :aria-label="item.label"
      @click="$emit('update:modelValue', item.value)"
    >
      <span class="shop-platform-switch__content">
        <img
          class="shop-platform-switch__icon"
          :src="item.icon"
          :alt="item.iconAlt"
        />
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

.shop-platform-switch__icon {
  width: var(--space-5);
  height: var(--space-5);
  border-radius: var(--radius-sm);
}

.shop-platform-switch__item--active {
  color: var(--accent-primary);
}
</style>
