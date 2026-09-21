<script setup lang="ts">
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

function formatCountWithUnit(value: number | null, unit: string): string {
  const formatted = formatDashboardCount(value)
  return value === null ? formatted : `${formatted} ${unit}`
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
  },
  {
    label: '成交订单',
    value: formatCountWithUnit(props.summary.orderCount, '单'),
    comparison: props.summary.orderComparison,
  },
  {
    label: '退货数量',
    value: formatCountWithUnit(props.summary.returnQuantity, '件'),
    comparison: props.summary.returnComparison,
  },
  {
    label: '店铺数量',
    value: formatCountWithUnit(props.summary.shopCount, '家'),
    comparison: props.summary.shopCountComparison,
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
</style>
