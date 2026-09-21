<script setup lang="ts">
import { computed } from 'vue'
import type { SelectOption } from 'naive-ui'
import { RefreshCw } from '@lucide/vue'

import FilterBar from '@/shared/components/FilterBar.vue'
import FilterField from '@/shared/components/FilterField.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppDatePicker, { type AppDateValue } from '@/shared/ui/AppDatePicker.vue'
import AppRadio from '@/shared/ui/AppRadio.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'
import type { AppOption, AppOptionValue } from '@/shared/ui/types'

import type {
  OperatingDashboardFilters,
} from '../model/types'

const props = defineProps<{
  modelValue: OperatingDashboardFilters
  shopOptions: SelectOption[]
  platformOptions: SelectOption[]
  refreshing?: boolean
  refreshAvailable: boolean
  refreshFeedback?: {
    tone: 'success' | 'warning' | 'error'
    message: string
  } | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: OperatingDashboardFilters]
  refresh: []
}>()

const dateOptions = [
  { label: '昨日', value: 'yesterday' },
  { label: '近3天', value: 'last3Days' },
  { label: '近7天', value: 'last7Days' },
  { label: '近30天', value: 'last30Days' },
  { label: '自定义', value: 'custom' },
] satisfies AppOption[]

function update<Key extends keyof OperatingDashboardFilters>(
  key: Key,
  value: OperatingDashboardFilters[Key],
): void {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

const datePreset = computed({
  get: () => props.modelValue.datePreset,
  set: (value: AppOptionValue) => {
    if (!dateOptions.some((option) => option.value === value)) return
    emit('update:modelValue', {
      ...props.modelValue,
      datePreset: value as OperatingDashboardFilters['datePreset'],
      customDateRange:
        value === 'custom' && props.modelValue.customDateRange === null
          ? [Date.now() - 86_400_000, Date.now()]
          : props.modelValue.customDateRange,
    })
  },
})
const customDateRange = computed({
  get: () => props.modelValue.customDateRange,
  set: (value: AppDateValue) =>
    update('customDateRange', Array.isArray(value) ? value : null),
})
const selectedShopId = computed({
  get: () => props.modelValue.shopId,
  set: (value: AppOptionValue | null) =>
    update('shopId', value === null ? null : String(value)),
})
const selectedPlatform = computed({
  get: () => props.modelValue.platform,
  set: (value: AppOptionValue | null) =>
    update(
      'platform',
      value === null ? null : (value as OperatingDashboardFilters['platform']),
    ),
})

function updateDatePreset(value: AppOptionValue): void {
  datePreset.value = value
}
</script>

<template>
  <div class="operating-dashboard-filter">
    <FilterBar>
      <AppRadio
        :model-value="datePreset"
        :options="dateOptions"
        @update:model-value="updateDatePreset"
      />
      <FilterField v-if="datePreset === 'custom'" width="md">
        <AppDatePicker
          v-model="customDateRange"
          type="daterange"
          :clearable="false"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
        />
      </FilterField>
      <FilterField width="sm">
        <AppSelect
          v-model="selectedShopId"
          width="sm"
          clearable
          filterable
          :options="shopOptions"
          placeholder="全部店铺"
        />
      </FilterField>
      <FilterField width="sm">
        <AppSelect
          v-model="selectedPlatform"
          width="sm"
          clearable
          :options="platformOptions"
          placeholder="全部平台"
        />
      </FilterField>
      <template #primary-action>
        <AppButton
          tone="primary"
          :loading="refreshing"
          :disabled="!refreshAvailable || refreshing"
          @click="$emit('refresh')"
        >
          <RefreshCw :size="16" aria-hidden="true" />
          更新数据
        </AppButton>
      </template>
    </FilterBar>
    <p
      v-if="refreshFeedback"
      class="operating-dashboard-filter__feedback"
      :class="`operating-dashboard-filter__feedback--${refreshFeedback.tone}`"
      role="status"
    >
      {{ refreshFeedback.message }}
    </p>
  </div>
</template>

<style scoped>
.operating-dashboard-filter {
  display: grid;
  gap: var(--space-2);
}

.operating-dashboard-filter__feedback {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.operating-dashboard-filter__feedback--success {
  color: var(--status-success);
}

.operating-dashboard-filter__feedback--warning {
  color: var(--status-warning);
}

.operating-dashboard-filter__feedback--error {
  color: var(--status-danger);
}

@media (max-width: 960px) {
  .operating-dashboard-filter :deep(.filter-bar) {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .operating-dashboard-filter :deep(.filter-bar__toolbar) {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>
