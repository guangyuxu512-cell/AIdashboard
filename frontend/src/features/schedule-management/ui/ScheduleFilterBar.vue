<script setup lang="ts">
import type { SelectOption } from 'naive-ui'
import { computed } from 'vue'

import FilterBar from '@/shared/components/FilterBar.vue'
import FilterField from '@/shared/components/FilterField.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'
import type { AppOptionValue } from '@/shared/ui/types'

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
</script>

<template>
  <FilterBar>
    <FilterField width="xs">
      <AppSelect
        v-model="enabled"
        width="xs"
        clearable
        :options="enabledOptions"
        placeholder="全部状态"
      />
    </FilterField>
    <FilterField width="sm">
      <AppSelect
        v-model="deviceId"
        width="sm"
        clearable
        filterable
        :options="deviceOptions"
        :loading="deviceOptionsLoading"
        placeholder="全部设备"
      />
    </FilterField>
    <FilterField width="md">
      <AppInput
        v-model="search"
        width="md"
        clearable
        placeholder="搜索计划名称或执行对象"
        @keyup.enter="$emit('query')"
      />
    </FilterField>
    <template #actions>
      <AppButton tone="text" @click="$emit('reset')">重置</AppButton>
      <AppButton tone="primary" @click="$emit('query')">查询</AppButton>
    </template>
    <template #primary-action>
      <AppButton tone="primary" @click="$emit('create')">+ 新建计划</AppButton>
    </template>
  </FilterBar>
</template>
