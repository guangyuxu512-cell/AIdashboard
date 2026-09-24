<script setup lang="ts">
import { NTooltip } from 'naive-ui'

import StatCard from '@/shared/components/StatCard.vue'
import SummaryGrid from '@/shared/components/SummaryGrid.vue'

import {
  formatDashboardComparison,
  formatDashboardCount,
  formatDashboardCurrency,
  getDashboardComparisonTone,
} from '../model/formatters'
import type {
  DashboardComparison,
  OperatingDashboardSummary,
} from '../model/types'

const props = defineProps<{
  summary: OperatingDashboardSummary
  comparisonLabel: string
}>()

function formatCountWithUnit(
  value: number | null,
  unit: string,
  partial = false,
): string {
  const formatted = formatDashboardCount(value)
  return value === null
    ? formatted
    : `${formatted}${partial ? '（部分）' : ''} ${unit}`
}

function getCardTone(
  comparison: DashboardComparison,
): 'neutral' | 'success' | 'error' {
  const tone = getDashboardComparisonTone(comparison)
  if (tone === 'positive') return 'success'
  if (tone === 'negative') return 'error'
  return 'neutral'
}

const cards = () => [
  {
    label: '成交金额',
    value: formatDashboardCurrency(props.summary.turnoverCents),
    comparison: props.summary.turnoverComparison,
    hint: undefined,
  },
  {
    label: '成交订单',
    value: formatCountWithUnit(props.summary.orderCount, '单'),
    comparison: props.summary.orderComparison,
    hint: undefined,
  },
  {
    label: '退款订单数',
    value: formatCountWithUnit(
      props.summary.refundOrderCount,
      '单',
      props.summary.refundOrderCoverageComplete === false &&
        props.summary.refundOrderCount !== null,
    ),
    comparison: props.summary.refundOrderComparison,
    hint:
      props.summary.refundOrderCoverageComplete === false
        ? '按退款时间统计；所选范围内仅部分日期有有效退款订单数据'
        : '按退款时间统计',
  },
  {
    label: '店铺数量',
    value: formatCountWithUnit(props.summary.shopCount, '家'),
    comparison: props.summary.shopCountComparison,
    hint: undefined,
  },
]
</script>

<template>
  <section aria-label="经营概览">
    <SummaryGrid :columns="4">
      <StatCard
        v-for="card in cards()"
        :key="card.label"
        :label="card.label"
        :value="card.value"
        :tone="getCardTone(card.comparison)"
      >
        <template #label>
          <NTooltip v-if="card.hint">
            <template #trigger>
              <span class="operating-dashboard-summary__metric-label">
                {{ card.label }}
              </span>
            </template>
            {{ card.hint }}
          </NTooltip>
          <template v-else>{{ card.label }}</template>
        </template>
        <template #description>
          <span class="operating-dashboard-summary__comparison">
            <span>{{ comparisonLabel }}</span>
            <span
              :class="`operating-dashboard-summary__comparison-value--${getDashboardComparisonTone(card.comparison)}`"
            >
              {{ formatDashboardComparison(card.comparison) }}
            </span>
          </span>
        </template>
      </StatCard>
    </SummaryGrid>
  </section>
</template>

<style scoped>
.operating-dashboard-summary__comparison {
  display: flex;
  gap: var(--space-2);
}

.operating-dashboard-summary__comparison-value--positive {
  color: var(--status-success);
}

.operating-dashboard-summary__comparison-value--negative {
  color: var(--status-danger);
}

.operating-dashboard-summary__comparison-value--neutral {
  color: var(--text-secondary);
}

.operating-dashboard-summary__metric-label {
  cursor: help;
}
</style>
