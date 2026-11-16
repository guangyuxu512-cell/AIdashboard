<script setup lang="ts">
import { computed } from 'vue'
import { NPopover, type SelectOption } from 'naive-ui'

import FilterBar from '@/shared/components/FilterBar.vue'
import FilterField from '@/shared/components/FilterField.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppDatePicker, { type AppDateValue } from '@/shared/ui/AppDatePicker.vue'
import AppRadio from '@/shared/ui/AppRadio.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'
import type { AppOption, AppOptionValue } from '@/shared/ui/types'

import type {
  OperatingDashboardCoverage,
  OperatingDashboardCoverageMissing,
  OperatingDashboardFilters,
} from '../model/types'
import { formatShanghaiDate } from '../model/dashboard'

const props = defineProps<{
  modelValue: OperatingDashboardFilters
  shopOptions: SelectOption[]
  platformOptions: SelectOption[]
  coverage?: OperatingDashboardCoverage | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: OperatingDashboardFilters]
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

const coverageText = computed(() => {
  const coverage = props.coverage
  if (!coverage) return null
  if (coverage.state === 'unsupported') return '当前筛选范围暂未支持经营采集'
  if (coverage.noOperatingScope) return '该范围尚未经营'
  if (
    coverage.collectedShopDays === 0 &&
    coverage.missingShopDays > 0 &&
    coverage.missingSamples.every((sample) => sample.state === 'missing')
  )
    return '所选范围尚未采集'
  return `所选范围已采集 ${coverage.collectedShopDays}/${coverage.totalShopDays} 个应采店铺日期`
})

const stateLabel: Record<
  OperatingDashboardCoverage['missingSamples'][number]['state'],
  string
> = {
  missing: '待采集',
  collecting: '采集中',
  waiting_collection_time: '等待每日采集时间',
  waiting_reauthorization: '等待重新登录',
  failed: '采集失败',
  unknown: '平台指标未知',
}

function coverageSampleText(sample: OperatingDashboardCoverageMissing): string {
  return `${sample.shopName} · ${sample.businessDate} · ${stateLabel[sample.state]}${
    sample.failureReason ? `（${sample.failureReason}）` : ''
  }`
}

const coverageDetail = computed(() => {
  const coverage = props.coverage
  if (!coverage || coverage.missingSamples.length === 0) return ''
  const samples = coverage.missingSamples.map(coverageSampleText)
  if (coverage.missingSamplesTruncated) samples.push('其余缺失项未展开')
  return samples.join('\n')
})

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
    </FilterBar>
    <p class="operating-dashboard-filter__coverage" role="status">经营数据采集已暂停，当前展示历史数据。</p>
    <p
      v-if="coverageText"
      class="operating-dashboard-filter__coverage"
      role="status"
    >
      {{ coverageText }}
      <NPopover
        v-if="coverageDetail"
        trigger="click"
        placement="bottom-start"
        scrollable
        style="max-height: min(60vh, 24rem)"
      >
        <template #trigger>
          <AppButton
            tone="text"
            class="operating-dashboard-filter__coverage-detail"
          >
            查看缺失
          </AppButton>
        </template>
        <div class="operating-dashboard-filter__coverage-tooltip">
          <div
            v-for="sample in coverage?.missingSamples ?? []"
            :key="`${sample.shopId}:${sample.businessDate}`"
            class="operating-dashboard-filter__missing-item"
          >
            <span>{{ coverageSampleText(sample) }}</span>
          </div>
          <span v-if="coverage?.missingSamplesTruncated">其余缺失项未展开</span>
        </div>
      </NPopover>
      <span
        v-if="(coverage?.shopsWithUnknownOperatingStart ?? 0) > 0"
        class="operating-dashboard-filter__coverage-note"
      >
        部分店铺经营起算日未确认，按完整日期范围统计
      </span>
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

.operating-dashboard-filter__coverage {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.operating-dashboard-filter__coverage-detail {
  margin-left: var(--space-2);
}

.operating-dashboard-filter__coverage-note {
  margin-left: var(--space-2);
}

.operating-dashboard-filter__coverage-tooltip {
  display: block;
  max-width: 22rem;
  white-space: pre-line;
}

.operating-dashboard-filter__missing-item {
  display: grid;
  justify-items: start;
  gap: var(--space-2);
  padding-block: var(--space-2);
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
