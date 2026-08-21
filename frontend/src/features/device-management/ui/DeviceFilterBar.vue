<script setup lang="ts">
import { computed } from 'vue'

import FilterBar from '@/shared/components/FilterBar.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppInput from '@/shared/ui/AppInput.vue'

import type { DeviceFilterViewModel } from '../model/types'

const props = defineProps<{
  modelValue: DeviceFilterViewModel
  statistics: { total: number; online: number; offline: number; error: number }
  refreshing?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: DeviceFilterViewModel]
  refresh: []
}>()

const keyword = computed({
  get: () => props.modelValue.keyword,
  set: (value: string) =>
    emit('update:modelValue', { ...props.modelValue, keyword: value }),
})
</script>

<template>
  <FilterBar>
    <div class="device-toolbar__statistics" aria-label="设备统计">
      <span
        >设备 <strong>{{ statistics.total }}</strong></span
      >
      <span class="device-toolbar__stat--online">
        在线 <strong>{{ statistics.online }}</strong>
      </span>
      <span
        >离线 <strong>{{ statistics.offline }}</strong></span
      >
      <span v-if="statistics.error" class="device-toolbar__stat--error">
        异常 <strong>{{ statistics.error }}</strong>
      </span>
    </div>

    <template #actions>
      <AppInput
        v-model="keyword"
        width="md"
        clearable
        placeholder="搜索设备名称或影刀账号"
      />
      <AppButton :loading="refreshing" @click="$emit('refresh')">
        刷新
      </AppButton>
    </template>

    <template #primary-action>
      <slot name="primary-action" />
    </template>
  </FilterBar>
</template>

<style scoped>
.device-toolbar__statistics {
  display: flex;
  align-items: center;
  gap: var(--space-5);
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
  white-space: nowrap;
}

.device-toolbar__statistics strong {
  margin-left: var(--space-1);
  color: var(--text-primary);
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-semibold);
}

.device-toolbar__stat--online strong {
  color: var(--color-success);
}

.device-toolbar__stat--error strong {
  color: var(--color-error);
}
</style>
