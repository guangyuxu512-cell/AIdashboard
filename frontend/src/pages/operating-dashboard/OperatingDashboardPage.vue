<script setup lang="ts">
import { computed, ref } from 'vue'

import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'
import ManagementListSection from '@/shared/components/ManagementListSection.vue'
import PageSection from '@/shared/components/PageSection.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'

import {
  OperatingDashboardFilterBar,
  OperatingDashboardSummaryCards,
  OperatingDashboardTable,
  OperatingDashboardTrendChart,
  useOperatingDashboard,
} from '@/features/operating-dashboard'

const dashboard = useOperatingDashboard()
const trendMetric = ref<'turnover' | 'orders'>('turnover')

const comparisonLabel = computed(() =>
  dashboard.filters.value.datePreset === 'yesterday' ? '较前日' : '较上期',
)
const trendTitle = computed(() => {
  const range = dashboard.read.value?.trendDateRange
  if (!range) return '成交趋势'
  return range.startDate === range.endDate
    ? `${range.endDate} 成交趋势`
    : `${range.startDate} 至 ${range.endDate} 成交趋势`
})
</script>

<template>
  <div class="page-container operating-dashboard-page">
    <PageSection v-if="dashboard.initialLoading.value">
      <LoadingState description="正在加载经营数据…" />
    </PageSection>

    <template v-else-if="dashboard.read.value">
      <OperatingDashboardSummaryCards
        :summary="dashboard.read.value.summary"
        :comparison-label="comparisonLabel"
      />

      <OperatingDashboardTrendChart
        v-model:metric="trendMetric"
        :title="trendTitle"
        :points="dashboard.read.value.trend"
      />

      <ManagementListSection class="operating-dashboard-page__list">
        <OperatingDashboardFilterBar
          :model-value="dashboard.filters.value"
          :shop-options="dashboard.shopOptions.value"
          :platform-options="dashboard.platformOptions.value"
          :refreshing="dashboard.refreshing.value"
          :refresh-available="dashboard.isMockMode"
          :refresh-feedback="dashboard.refreshFeedback.value"
          @update:model-value="dashboard.updateFilters"
          @refresh="dashboard.refresh"
        />

        <OperatingDashboardTable
          :rows="dashboard.rows.value"
          :loading="dashboard.filterLoading.value"
          :empty-description="dashboard.tableEmptyDescription.value"
        />

        <PaginationBar
          v-model:page="dashboard.page.value"
          :page-size="dashboard.pageSize.value"
          :item-count="dashboard.total.value"
          @update:page-size="dashboard.setPageSize"
        />
      </ManagementListSection>
    </template>

    <PageSection v-else>
      <ErrorState title="经营数据暂不可用" />
    </PageSection>
  </div>
</template>

<style scoped>
.operating-dashboard-page {
  height: 100%;
  min-height: 0;
}

</style>
