<script setup lang="ts">
import { computed } from 'vue'
import type { SelectOption } from 'naive-ui'

import {
  SHOP_OPERATIONAL_STATUS_META,
  SHOP_OWNER_FIXTURE_OPTIONS,
  SHOP_PLATFORM_FIXTURE_OPTIONS,
  SHOP_SESSION_STATUS_META,
  type ShopOperationalStatus,
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

const props = defineProps<{ modelValue: ShopFilterViewModel }>()

const emit = defineEmits<{
  'update:modelValue': [value: ShopFilterViewModel]
  query: []
  reset: []
}>()

const operationalStatusOptions: SelectOption[] = Object.entries(
  SHOP_OPERATIONAL_STATUS_META,
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

const operationalStatus = computed({
  get: () => props.modelValue.operationalStatus,
  set: (value: AppOptionValue | null) =>
    updateFilter('operationalStatus', value as ShopOperationalStatus | null),
})

const sessionStatus = computed({
  get: () => props.modelValue.sessionStatus,
  set: (value: AppOptionValue | null) =>
    updateFilter('sessionStatus', value as ShopSessionStatus | null),
})

const ownerName = computed({
  get: () => props.modelValue.ownerName,
  set: (value: AppOptionValue | null) =>
    updateFilter('ownerName', value as string | null),
})

const keyword = computed({
  get: () => props.modelValue.keyword,
  set: (value: string) => updateFilter('keyword', value),
})
</script>

<template>
  <FilterBar>
    <FilterField label="平台">
      <AppSelect
        v-model="platform"
        width="sm"
        clearable
        :options="SHOP_PLATFORM_FIXTURE_OPTIONS"
        placeholder="全部平台"
      />
    </FilterField>
    <FilterField label="店铺状态">
      <AppSelect
        v-model="operationalStatus"
        width="sm"
        clearable
        :options="operationalStatusOptions"
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
        v-model="ownerName"
        width="sm"
        clearable
        :options="SHOP_OWNER_FIXTURE_OPTIONS"
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
    <template #actions>
      <AppButton tone="text" @click="$emit('reset')">重置</AppButton>
      <AppButton tone="primary" @click="$emit('query')">查询</AppButton>
    </template>
  </FilterBar>
</template>
