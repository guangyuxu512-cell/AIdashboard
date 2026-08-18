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
const isDevelopment = import.meta.env.DEV

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
    <span v-if="!available && isDevelopment" class="filter-unavailable">
      Backend V1 暂未提供设备列表筛选参数；当前仅使用服务端分页。
    </span>
    <template v-else>
      <FilterField label="设备状态">
        <AppSelect
          v-model="status"
          width="sm"
          clearable
          :options="DEVICE_STATUS_FIXTURE_OPTIONS"
          placeholder="全部状态"
        />
      </FilterField>
      <FilterField label="设备标签">
        <AppSelect
          v-model="tag"
          width="sm"
          clearable
          :options="DEVICE_TAG_FIXTURE_OPTIONS"
          placeholder="全部标签"
        />
      </FilterField>
      <FilterField label="Worker 版本">
        <AppSelect
          v-model="workerVersion"
          width="sm"
          clearable
          :options="DEVICE_WORKER_VERSION_FIXTURE_OPTIONS"
          placeholder="全部版本"
        />
      </FilterField>
      <FilterField label="执行能力">
        <AppSelect
          v-model="capability"
          width="sm"
          clearable
          :options="DEVICE_CAPABILITY_FIXTURE_OPTIONS"
          placeholder="全部能力"
        />
      </FilterField>
      <FilterField label="关键词" width="md">
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
  </FilterBar>
</template>

<style scoped>
.filter-unavailable {
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
}
</style>
