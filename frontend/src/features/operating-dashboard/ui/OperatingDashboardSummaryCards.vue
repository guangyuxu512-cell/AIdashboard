<script setup lang="ts">
import PageSection from '@/shared/components/PageSection.vue'

import {
  formatDashboardComparison,
  formatDashboardCount,
  formatDashboardCurrency,
  getDashboardComparisonTone,
} from '../model/formatters'
import type { OperatingDashboardSummary } from '../model/types'

const props = defineProps<{
  summary: OperatingDashboardSummary
  comparisonLabel: string
}>()

function formatCountWithUnit(value: number | null, unit: string): string {
  const formatted = formatDashboardCount(value)
  return value === null ? formatted : `${formatted} ${unit}`
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
  <section class="operating-dashboard-summary" aria-label="经营概览">
    <PageSection
      v-for="card in cards()"
      :key="card.label"
      class="operating-dashboard-summary__card"
    >
      <div class="operating-dashboard-summary__label">{{ card.label }}</div>
      <strong class="operating-dashboard-summary__value">{{ card.value }}</strong>
      <div class="operating-dashboard-summary__comparison">
        <span>{{ comparisonLabel }}</span>
        <span
          :class="`operating-dashboard-summary__comparison-value--${getDashboardComparisonTone(card.comparison)}`"
        >
          {{ formatDashboardComparison(card.comparison) }}
        </span>
      </div>
    </PageSection>
  </section>
</template>

<style scoped>
.operating-dashboard-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--layout-card-gap);
}

.operating-dashboard-summary__card :deep(.page-section__content) {
  display: grid;
  gap: var(--space-2);
}

.operating-dashboard-summary__label {
  color: var(--text-secondary);
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-medium);
}

.operating-dashboard-summary__value {
  color: var(--text-primary);
  font-size: calc(var(--font-size-page-title) + var(--space-2));
  font-weight: var(--font-weight-semibold);
  line-height: 1.1;
}

.operating-dashboard-summary__comparison {
  display: flex;
  gap: var(--space-2);
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
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

@media (max-width: 1040px) {
  .operating-dashboard-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 620px) {
  .operating-dashboard-summary {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
