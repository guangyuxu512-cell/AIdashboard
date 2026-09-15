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
import { useAutoSearch } from '@/shared/composables/useAutoSearch'

import type { ShopFilterViewModel } from '../model/types'

const props = defineProps<{
  modelValue: ShopFilterViewModel
  ownerOptions: SelectOption[]
  ownerOptionsLoading?: boolean
  showOwnerFilter?: boolean
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
const autoSearch = useAutoSearch(() => emit('query'))

function applySelectFilter<Key extends 'enabledStatus' | 'ownerUserId'>(
  key: Key,
  value: ShopFilterViewModel[Key],
): void {
  updateFilter(key, value)
  autoSearch.submitNow()
}

function resetFilters(): void {
  autoSearch.cancel()
  emit('reset')
}
</script>

<template>
  <FilterBar>
    <FilterField>
      <AppSelect
        :model-value="enabledStatus"
        width="sm"
        clearable
        :options="enabledStatusOptions"
        placeholder="全部状态"
        @update:model-value="applySelectFilter('enabledStatus', $event as ShopEnabledStatus | null)"
      />
    </FilterField>
    <FilterField v-if="showOwnerFilter">
      <AppSelect
        :model-value="ownerUserId"
        width="sm"
        clearable
        :options="ownerOptions"
        :loading="ownerOptionsLoading"
        placeholder="全部负责人"
        @update:model-value="applySelectFilter('ownerUserId', $event as string | null)"
      />
    </FilterField>
    <FilterField width="md">
      <AppInput
        v-model="keyword"
        width="md"
        clearable
        placeholder="搜索店铺名称"
        @update:model-value="autoSearch.onInput"
        @compositionstart="autoSearch.onCompositionStart"
        @compositionend="autoSearch.onCompositionEnd(keyword)"
        @keyup.enter="autoSearch.onEnter($event)"
      />
    </FilterField>
    <template #actions>
      <AppButton tone="text" @click="resetFilters">重置</AppButton>
    </template>
    <template v-if="$slots['primary-action']" #primary-action>
      <slot name="primary-action" />
    </template>
  </FilterBar>
</template>
