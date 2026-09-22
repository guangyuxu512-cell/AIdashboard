<script setup lang="ts">
import { computed } from 'vue'
import { NTooltip, type SelectOption } from 'naive-ui'
import { RefreshCw } from '@lucide/vue'

import FilterBar from '@/shared/components/FilterBar.vue'
import FilterField from '@/shared/components/FilterField.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppDatePicker, { type AppDateValue } from '@/shared/ui/AppDatePicker.vue'
import AppRadio from '@/shared/ui/AppRadio.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'
import type { AppOption, AppOptionValue } from '@/shared/ui/types'

import type { OperatingDashboardFilters } from '../model/types'
import { formatShanghaiDate } from '../model/dashboard'

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

const SHANGHAI_DAY_MS = 86_400_000

function latestCompletedDateTimestamp(): number {
  const today = formatShanghaiDate(new Date())
  return Date.parse(`${today}T00:00:00+08:00`) - SHANGHAI_DAY_MS
}

function disableUnfinishedBusinessDate(timestamp: number): boolean {
  return (
    formatShanghaiDate(new Date(timestamp)) >= formatShanghaiDate(new Date())
  )
}

/** UI-only option values are normalized to null before emitting domain filters. */
const ALL_SHOPS_OPTION_VALUE = '__operating_dashboard_all_shops__'
const ALL_PLATFORMS_OPTION_VALUE = '__operating_dashboard_all_platforms__'

const shopSelectOptions = computed<SelectOption[]>(() => [
  { label: '全部店铺', value: ALL_SHOPS_OPTION_VALUE },
  ...props.shopOptions,
])
const platformSelectOptions = computed<SelectOption[]>(() => [
  { label: '全部平台', value: ALL_PLATFORMS_OPTION_VALUE },
  ...props.platformOptions,
])

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
          ? [
              latestCompletedDateTimestamp() - SHANGHAI_DAY_MS,
              latestCompletedDateTimestamp(),
            ]
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
  get: () => props.modelValue.shopId ?? ALL_SHOPS_OPTION_VALUE,
  set: (value: AppOptionValue | null) =>
    update(
      'shopId',
      value === null || value === ALL_SHOPS_OPTION_VALUE ? null : String(value),
    ),
})
const selectedPlatform = computed({
  get: () => props.modelValue.platform ?? ALL_PLATFORMS_OPTION_VALUE,
  set: (value: AppOptionValue | null) =>
    update(
      'platform',
      value === null || value === ALL_PLATFORMS_OPTION_VALUE
        ? null
        : (value as OperatingDashboardFilters['platform']),
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
      <AppDatePicker
        v-if="datePreset === 'custom'"
        v-model="customDateRange"
        type="daterange"
        :clearable="false"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        :is-date-disabled="disableUnfinishedBusinessDate"
      />
      <FilterField width="sm">
        <AppSelect
          v-model="selectedShopId"
          width="sm"
          clearable
          filterable
          :options="shopSelectOptions"
          placeholder="全部店铺"
        />
      </FilterField>
      <FilterField width="sm">
        <AppSelect
          v-model="selectedPlatform"
          width="sm"
          clearable
          :options="platformSelectOptions"
          placeholder="全部平台"
        />
      </FilterField>
      <template #primary-action>
        <NTooltip v-if="!refreshAvailable">
          <template #trigger>
            <span class="operating-dashboard-filter__refresh-trigger">
              <AppButton tone="primary" disabled>
                <RefreshCw :size="16" aria-hidden="true" />
                更新数据
              </AppButton>
            </span>
          </template>
          经营数据更新暂不可用
        </NTooltip>
        <AppButton
          v-else
          tone="primary"
          :loading="refreshing"
          :disabled="refreshing"
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

.operating-dashboard-filter__refresh-trigger {
  display: inline-flex;
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
