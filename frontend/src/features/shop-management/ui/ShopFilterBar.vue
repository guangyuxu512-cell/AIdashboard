<script setup lang="ts">
import { computed } from 'vue'
import type { SelectOption } from 'naive-ui'

import {
  SHOP_ENABLED_STATUS_META,
  type ShopEnabledStatus,
} from '@/entities/shop'
import FilterBar from '@/shared/components/FilterBar.vue'
import FilterField from '@/shared/components/FilterField.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'
import type { AppOptionValue } from '@/shared/ui/types'

import type { ShopFilterViewModel } from '../model/types'

const props = defineProps<{
  modelValue: ShopFilterViewModel
  ownerOptions: SelectOption[]
  ownerOptionsLoading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: ShopFilterViewModel]
  query: []
  reset: []
}>()

const enabledStatusOptions: SelectOption[] = Object.entries(
  SHOP_ENABLED_STATUS_META,
).map(([value, meta]) => ({ label: meta.label, value }))

function updateFilter<Key extends keyof ShopFilterViewModel>(
  key: Key,
  value: ShopFilterViewModel[Key],
): void {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

const enabledStatus = computed({
  get: () => props.modelValue.enabledStatus,
  set: (value: AppOptionValue | null) =>
    updateFilter('enabledStatus', value as ShopEnabledStatus | null),
})

const ownerUserId = computed({
  get: () => props.modelValue.ownerUserId,
  set: (value: AppOptionValue | null) =>
    updateFilter('ownerUserId', value as string | null),
})

const keyword = computed({
  get: () => props.modelValue.keyword,
  set: (value: string) => updateFilter('keyword', value),
})
</script>

<template>
  <FilterBar>
    <FilterField label="店铺状态">
      <AppSelect
        v-model="enabledStatus"
        width="sm"
        clearable
        :options="enabledStatusOptions"
        placeholder="全部状态"
      />
    </FilterField>
    <FilterField label="负责人">
      <AppSelect
        v-model="ownerUserId"
        width="sm"
        clearable
        :options="ownerOptions"
        :loading="ownerOptionsLoading"
        placeholder="全部负责人"
      />
    </FilterField>
    <FilterField label="关键词" width="md">
      <AppInput
        v-model="keyword"
        width="md"
        clearable
        placeholder="搜索店铺名称"
        @keyup.enter="$emit('query')"
      />
    </FilterField>
    <template #actions>
      <span class="shop-filter-bar__scope">筛选当前页</span>
      <AppButton tone="text" @click="$emit('reset')">重置</AppButton>
      <AppButton tone="primary" @click="$emit('query')">查询</AppButton>
    </template>
  </FilterBar>
</template>

<style scoped>
.shop-filter-bar__scope {
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
  white-space: nowrap;
}
</style>
