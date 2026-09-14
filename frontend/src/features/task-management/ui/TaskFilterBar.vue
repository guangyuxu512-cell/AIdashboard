<script setup lang="ts">
import type { SelectOption } from 'naive-ui'
import dayjs from 'dayjs'
import { computed } from 'vue'

import { TASK_STATUS_META, type TaskStatusDto } from '@/entities/task'
import FilterBar from '@/shared/components/FilterBar.vue'
import FilterField from '@/shared/components/FilterField.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppDatePicker, { type AppDateValue } from '@/shared/ui/AppDatePicker.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'
import type { AppOptionValue } from '@/shared/ui/types'
import { useAutoSearch } from '@/shared/composables/useAutoSearch'

import type { TaskDatePreset, TaskFilterViewModel } from '../model/types'

const props = defineProps<{
  modelValue: TaskFilterViewModel
  deviceOptions: SelectOption[]
  deviceOptionsLoading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: TaskFilterViewModel]
  query: []
  reset: []
}>()

const statusOptions: SelectOption[] = Object.entries(TASK_STATUS_META).map(
  ([value, meta]) => ({ label: meta.label, value }),
)
const datePresetOptions: SelectOption[] = [
  { label: '今天', value: 'today' },
  { label: '昨天', value: 'yesterday' },
  { label: '最近 7 天', value: 'last7Days' },
  { label: '最近 30 天', value: 'last30Days' },
  { label: '自定义', value: 'custom' },
  { label: '全部时间', value: 'all' },
]

function updateFilter<Key extends keyof TaskFilterViewModel>(
  key: Key,
  value: TaskFilterViewModel[Key],
): void {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

const status = computed({
  get: () => props.modelValue.status,
  set: (value: AppOptionValue | null) =>
    updateFilter('status', value as TaskStatusDto | null),
})
const deviceId = computed({
  get: () => props.modelValue.deviceId,
  set: (value: AppOptionValue | null) =>
    updateFilter('deviceId', value as string | null),
})
const datePreset = computed({
  get: () => props.modelValue.datePreset,
  set: (value: AppOptionValue | null) => {
    const preset = (value ?? 'last7Days') as TaskDatePreset
    const today = dayjs().startOf('day')
    emit('update:modelValue', {
      ...props.modelValue,
      datePreset: preset,
      customDateRange:
        preset === 'custom' && !props.modelValue.customDateRange
          ? [today.subtract(6, 'day').valueOf(), today.valueOf()]
          : props.modelValue.customDateRange,
    })
  },
})
const customDateRange = computed({
  get: () => props.modelValue.customDateRange,
  set: (value: AppDateValue) =>
    updateFilter('customDateRange', Array.isArray(value) ? value : null),
})
const search = computed({
  get: () => props.modelValue.search,
  set: (value: string) => updateFilter('search', value),
})
const autoSearch = useAutoSearch(() => emit('query'))

function applyFilter<Key extends keyof TaskFilterViewModel>(
  key: Key,
  value: TaskFilterViewModel[Key],
): void {
  updateFilter(key, value)
  autoSearch.submitNow()
}

function resetFilters(): void {
  autoSearch.cancel()
  emit('reset')
}

function applyDatePreset(value: AppOptionValue | null): void {
  datePreset.value = (value ?? 'last7Days') as TaskDatePreset
  autoSearch.submitNow()
}
</script>

<template>
  <FilterBar>
    <FilterField width="xs">
      <AppSelect
        :model-value="status"
        width="xs"
        clearable
        :options="statusOptions"
        placeholder="全部状态"
        @update:model-value="applyFilter('status', $event as TaskStatusDto | null)"
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
    <FilterField width="xs">
      <AppSelect
        :model-value="datePreset"
        width="xs"
        :options="datePresetOptions"
        placeholder="创建时间"
        @update:model-value="applyDatePreset"
      />
    </FilterField>
    <AppDatePicker
      v-if="datePreset === 'custom'"
      v-model="customDateRange"
      type="daterange"
      :clearable="false"
      start-placeholder="开始日期"
      end-placeholder="结束日期"
      @update:model-value="autoSearch.submitNow"
    />
    <FilterField width="md">
      <AppInput
        v-model="search"
        width="md"
        clearable
        placeholder="搜索 Task ID / 执行对象 / Skill"
        @update:model-value="autoSearch.onInput"
        @compositionstart="autoSearch.onCompositionStart"
        @compositionend="autoSearch.onCompositionEnd(search)"
        @keyup.enter="autoSearch.onEnter($event)"
      />
    </FilterField>
    <template #actions>
      <AppButton tone="text" @click="resetFilters">重置</AppButton>
    </template>
  </FilterBar>
</template>
