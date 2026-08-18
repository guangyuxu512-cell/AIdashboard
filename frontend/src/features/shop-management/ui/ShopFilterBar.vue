<script setup lang="ts">
import { computed } from 'vue'
import type { SelectOption } from 'naive-ui'

import {
  SHOP_ENABLED_STATUS_META,
  SHOP_SESSION_STATUS_META,
  type ShopEnabledStatus,
  type ShopPlatform,
  type ShopSessionStatus,
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
  available: boolean
  platformOptions: SelectOption[]
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

const sessionStatusOptions: SelectOption[] = Object.entries(
  SHOP_SESSION_STATUS_META,
).map(([value, meta]) => ({ label: meta.label, value }))

function updateFilter<Key extends keyof ShopFilterViewModel>(
  key: Key,
  value: ShopFilterViewModel[Key],
): void {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

const platform = computed({
  get: () => props.modelValue.platform,
  set: (value: AppOptionValue | null) =>
    updateFilter('platform', value as ShopPlatform | null),
})

const enabledStatus = computed({
  get: () => props.modelValue.enabledStatus,
  set: (value: AppOptionValue | null) =>
    updateFilter('enabledStatus', value as ShopEnabledStatus | null),
})

const sessionStatus = computed({
  get: () => props.modelValue.sessionStatus,
  set: (value: AppOptionValue | null) =>
    updateFilter('sessionStatus', value as ShopSessionStatus | null),
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
    <span v-if="!available" class="filter-unavailable">
      Backend V1 暂未提供店铺列表筛选参数；当前仅使用服务端分页。
    </span>
    <template v-else>
      <FilterField label="平台">
        <AppSelect
          v-model="platform"
          width="sm"
          clearable
          :options="platformOptions"
          placeholder="全部平台"
        />
      </FilterField>
      <FilterField label="启用状态">
        <AppSelect
          v-model="enabledStatus"
          width="sm"
          clearable
          :options="enabledStatusOptions"
          placeholder="全部状态"
        />
      </FilterField>
      <FilterField label="会话状态">
        <AppSelect
          v-model="sessionStatus"
          width="sm"
          clearable
          :options="sessionStatusOptions"
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
          placeholder="店铺、负责人或设备"
          @keyup.enter="$emit('query')"
        />
      </FilterField>
    </template>
    <template #actions>
      <template v-if="available">
        <AppButton tone="text" @click="$emit('reset')">重置</AppButton>
        <AppButton tone="primary" @click="$emit('query')">查询</AppButton>
      </template>
    </template>
  </FilterBar>
</template>

<style scoped>
.filter-unavailable {
  color: var(--color-text-secondary);
  font-size: var(--font-size-secondary);
}
</style>
