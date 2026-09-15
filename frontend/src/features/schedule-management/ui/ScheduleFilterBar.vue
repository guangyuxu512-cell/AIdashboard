<script setup lang="ts">
import type { SelectOption } from 'naive-ui'
import { computed } from 'vue'

import FilterBar from '@/shared/components/FilterBar.vue'
import FilterField from '@/shared/components/FilterField.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppDatePicker from '@/shared/ui/AppDatePicker.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import AppRadio from '@/shared/ui/AppRadio.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'
import type { AppOptionValue } from '@/shared/ui/types'
import { useAutoSearch } from '@/shared/composables/useAutoSearch'

import type { ScheduleFilterViewModel } from '../model/types'

const props = defineProps<{
  modelValue: ScheduleFilterViewModel
  deviceOptions: SelectOption[]
  deviceOptionsLoading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: ScheduleFilterViewModel]
  query: []
  reset: []
  create: []
}>()

const enabledOptions: SelectOption[] = [
  { label: '已开启', value: 'enabled' },
  { label: '已停用', value: 'disabled' },
]
const occurrenceOptions = [
  { label: '全部日期', value: 'all' },
  { label: '今天', value: 'today' },
  { label: '指定日期', value: 'selected' },
]

function update<Key extends keyof ScheduleFilterViewModel>(
  key: Key,
  value: ScheduleFilterViewModel[Key],
): void {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

const enabled = computed({
  get: () =>
    props.modelValue.enabled === null
      ? null
      : props.modelValue.enabled
        ? 'enabled'
        : 'disabled',
  set: (value: AppOptionValue | null) =>
    update('enabled', value === null ? null : value === 'enabled'),
})
const deviceId = computed({
  get: () => props.modelValue.deviceId,
  set: (value: AppOptionValue | null) =>
    update('deviceId', value as string | null),
})
const search = computed({
  get: () => props.modelValue.search,
  set: (value: string) => update('search', value),
})
const occurrenceMode = computed({
  get: () => props.modelValue.occurrenceMode,
  set: (value: AppOptionValue | null) => {
    if (value !== 'all' && value !== 'today' && value !== 'selected') return
    emit('update:modelValue', {
      ...props.modelValue,
      occurrenceMode: value,
      selectedOccurrenceDate:
        value === 'selected' && props.modelValue.selectedOccurrenceDate === null
          ? Date.now()
          : props.modelValue.selectedOccurrenceDate,
    })
  },
})
const selectedOccurrenceDate = computed({
  get: () => props.modelValue.selectedOccurrenceDate,
  set: (value: number | [number, number] | null) =>
    update('selectedOccurrenceDate', typeof value === 'number' ? value : null),
})
const autoSearch = useAutoSearch(() => emit('query'))

function applyFilter<Key extends 'enabled' | 'deviceId'>(
  key: Key,
  value: ScheduleFilterViewModel[Key],
): void {
  update(key, value)
  autoSearch.submitNow()
}

function resetFilters(): void {
  autoSearch.cancel()
  emit('reset')
}
</script>

<template>
  <FilterBar>
    <FilterField width="xs">
      <AppSelect
        :model-value="enabled"
        width="xs"
        clearable
        :options="enabledOptions"
        placeholder="全部状态"
        @update:model-value="applyFilter('enabled', $event === null ? null : $event === 'enabled')"
      />
    </FilterField>
    <FilterField width="sm">
      <AppSelect
        :model-value="deviceId"
        width="sm"
        clearable
        filterable
        :options="deviceOptions"
        :loading="deviceOptionsLoading"
        placeholder="全部设备"
        @update:model-value="applyFilter('deviceId', $event as string | null)"
      />
    </FilterField>
    <FilterField width="md">
      <AppRadio
        v-model="occurrenceMode"
        :options="occurrenceOptions"
        @update:model-value="autoSearch.submitNow"
      />
    </FilterField>
    <FilterField v-if="occurrenceMode === 'selected'" width="sm">
      <AppDatePicker
        v-model="selectedOccurrenceDate"
        placeholder="选择发生日期"
        @update:model-value="autoSearch.submitNow"
      />
    </FilterField>
    <FilterField width="md">
      <AppInput
        v-model="search"
        width="md"
        clearable
        placeholder="搜索计划名称或执行对象"
        @update:model-value="autoSearch.onInput"
        @compositionstart="autoSearch.onCompositionStart"
        @compositionend="autoSearch.onCompositionEnd(search)"
        @keyup.enter="autoSearch.onEnter($event)"
      />
    </FilterField>
    <template #actions>
      <AppButton tone="text" @click="resetFilters">重置</AppButton>
    </template>
    <template #primary-action>
      <AppButton tone="primary" @click="$emit('create')">+ 新建计划</AppButton>
    </template>
  </FilterBar>
</template>
