<script setup lang="ts">
import type { SelectOption } from 'naive-ui'
import { computed } from 'vue'

import { TASK_STATUS_META, type TaskStatusDto } from '@/entities/task'
import FilterBar from '@/shared/components/FilterBar.vue'
import FilterField from '@/shared/components/FilterField.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'
import type { AppOptionValue } from '@/shared/ui/types'

import type { TaskFilterViewModel } from '../model/types'

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
const search = computed({
  get: () => props.modelValue.search,
  set: (value: string) => updateFilter('search', value),
})
</script>

<template>
  <FilterBar>
    <FilterField>
      <AppSelect
        v-model="status"
        width="sm"
        clearable
        :options="statusOptions"
        placeholder="全部状态"
      />
    </FilterField>
    <FilterField>
      <AppSelect
        v-model="deviceId"
        width="md"
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
        placeholder="搜索 Task ID / 执行对象 / Skill"
        @keyup.enter="$emit('query')"
      />
    </FilterField>
    <template #actions>
      <AppButton tone="text" @click="$emit('reset')">重置</AppButton>
      <AppButton tone="primary" @click="$emit('query')">查询</AppButton>
    </template>
  </FilterBar>
</template>
