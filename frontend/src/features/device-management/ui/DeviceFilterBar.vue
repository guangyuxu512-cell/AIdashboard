<script setup lang="ts">
import { computed } from 'vue'

import {
  DEVICE_CAPABILITY_FIXTURE_OPTIONS,
  DEVICE_STATUS_FIXTURE_OPTIONS,
  DEVICE_TAG_FIXTURE_OPTIONS,
  DEVICE_WORKER_VERSION_FIXTURE_OPTIONS,
  type DeviceCapability,
  type DeviceStatus,
} from '@/entities/device'
import FilterBar from '@/shared/components/FilterBar.vue'
import FilterField from '@/shared/components/FilterField.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'
import type { AppOptionValue } from '@/shared/ui/types'

import type { DeviceFilterViewModel } from '../model/types'

const props = defineProps<{
  modelValue: DeviceFilterViewModel
  available: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: DeviceFilterViewModel]
  query: []
  reset: []
}>()
function updateFilter<Key extends keyof DeviceFilterViewModel>(
  key: Key,
  value: DeviceFilterViewModel[Key],
): void {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

const status = computed({
  get: () => props.modelValue.status,
  set: (value: AppOptionValue | null) =>
    updateFilter('status', value as DeviceStatus | null),
})

const tag = computed({
  get: () => props.modelValue.tag,
  set: (value: AppOptionValue | null) =>
    updateFilter('tag', value as string | null),
})

const workerVersion = computed({
  get: () => props.modelValue.workerVersion,
  set: (value: AppOptionValue | null) =>
    updateFilter('workerVersion', value as string | null),
})

const capability = computed({
  get: () => props.modelValue.capability,
  set: (value: AppOptionValue | null) =>
    updateFilter('capability', value as DeviceCapability | null),
})

const keyword = computed({
  get: () => props.modelValue.keyword,
  set: (value: string) => updateFilter('keyword', value),
})
</script>

<template>
  <FilterBar>
    <template v-if="available">
      <FilterField>
        <AppSelect
          v-model="status"
          width="sm"
          clearable
          :options="DEVICE_STATUS_FIXTURE_OPTIONS"
          placeholder="全部状态"
        />
      </FilterField>
      <FilterField>
        <AppSelect
          v-model="tag"
          width="sm"
          clearable
          :options="DEVICE_TAG_FIXTURE_OPTIONS"
          placeholder="全部标签"
        />
      </FilterField>
      <FilterField>
        <AppSelect
          v-model="workerVersion"
          width="sm"
          clearable
          :options="DEVICE_WORKER_VERSION_FIXTURE_OPTIONS"
          placeholder="全部版本"
        />
      </FilterField>
      <FilterField>
        <AppSelect
          v-model="capability"
          width="sm"
          clearable
          :options="DEVICE_CAPABILITY_FIXTURE_OPTIONS"
          placeholder="全部能力"
        />
      </FilterField>
      <FilterField width="md">
        <AppInput
          v-model="keyword"
          width="md"
          clearable
          placeholder="设备、位置、系统或标签"
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
    <template v-if="$slots['primary-action']" #primary-action>
      <slot name="primary-action" />
    </template>
  </FilterBar>
</template>
