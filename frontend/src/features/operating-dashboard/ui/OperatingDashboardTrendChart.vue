<script setup lang="ts">
import { init, use, type ECharts, type EChartsCoreOption } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import PageSection from '@/shared/components/PageSection.vue'
import AppRadio from '@/shared/ui/AppRadio.vue'
import { useThemeStore } from '@/stores/theme'

import {
  formatDashboardCount,
  formatDashboardCurrency,
} from '../model/formatters'
import type { OperatingDashboardTrendPoint } from '../model/types'

type TrendMetric = 'turnover' | 'orders'

use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

const props = defineProps<{
  title: string
  points: OperatingDashboardTrendPoint[]
  metric: TrendMetric
}>()

const emit = defineEmits<{
  'update:metric': [value: TrendMetric]
}>()

const themeStore = useThemeStore()
const chartElement = ref<HTMLElement | null>(null)
let chart: ECharts | null = null
let resizeObserver: ResizeObserver | null = null

const metricOptions = [
  { label: '成交金额', value: 'turnover' },
  { label: '成交订单数', value: 'orders' },
] satisfies Array<{ label: string; value: TrendMetric }>

const chartOption = computed<EChartsCoreOption>(() => {
  // CSS reads are not reactive: depend on the preset, including light→light.
  void themeStore.resolvedPreset
  const root = document.documentElement
  const styles = getComputedStyle(root)
  const primary = styles.getPropertyValue('--chart-primary').trim()
  const textSecondary = styles.getPropertyValue('--text-tertiary').trim()
  const textPrimary = styles.getPropertyValue('--text-primary').trim()
  const border = styles.getPropertyValue('--border-subtle').trim()
  const surface = styles.getPropertyValue('--bg-surface-solid').trim()
  const isTurnover = props.metric === 'turnover'
  const values = props.points.map((point) => {
    const value = isTurnover ? point.turnoverCents : point.orderCount
    return isTurnover && value !== null ? value / 100 : value
  })

  return {
    animationDuration: 180,
    grid: { top: 18, right: 20, bottom: 30, left: isTurnover ? 62 : 48 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: props.points.map((point) =>
        point.businessDate.slice(5).replace('-', '/'),
      ),
      axisLine: { lineStyle: { color: border } },
      axisLabel: { color: textSecondary },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisLabel: {
        color: textSecondary,
        formatter: (value: number) =>
          isTurnover ? `¥${value.toLocaleString('zh-CN')}` : String(value),
      },
      splitLine: { lineStyle: { color: border, type: 'dashed' } },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: surface,
      borderColor: border,
      textStyle: { color: textPrimary },
      formatter: (params: unknown) => {
        const point = Array.isArray(params) ? params[0] : params
        if (!point || typeof point !== 'object') return ''
        const typedPoint = point as {
          axisValueLabel?: string
          dataIndex?: number
          value?: number | null
        }
        const value = typedPoint.value ?? null
        const coverageComplete =
          props.points[typedPoint.dataIndex ?? -1]?.coverageComplete
        const display = isTurnover
          ? formatDashboardCurrency(value === null ? null : value * 100)
          : formatDashboardCount(value)
        const coverageNote =
          value !== null && coverageComplete === false ? '（覆盖不完整）' : ''
        return `${typedPoint.axisValueLabel ?? ''}<br/>${isTurnover ? '成交金额' : '成交订单数'}：${display}${coverageNote}`
      },
    },
    series: [
      {
        type: 'line',
        smooth: true,
        connectNulls: false,
        showSymbol: true,
        symbolSize: 7,
        data: values,
        lineStyle: { width: 2, color: primary },
        itemStyle: { color: primary },
        areaStyle: { color: primary, opacity: 0.08 },
      },
    ],
  }
})

function updateMetric(value: string | number): void {
  if (value === 'turnover' || value === 'orders') emit('update:metric', value)
}

function renderChart(): void {
  if (!chartElement.value) return
  if (!chart) chart = init(chartElement.value)
  chart.setOption(chartOption.value, true)
}

onMounted(async () => {
  await nextTick()
  renderChart()
  if (chartElement.value) {
    resizeObserver = new ResizeObserver(() => chart?.resize())
    resizeObserver.observe(chartElement.value)
  }
})

watch(chartOption, renderChart, {
  deep: true,
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  chart?.dispose()
  chart = null
})
</script>

<template>
  <PageSection class="operating-dashboard-trend" :title="title">
    <template #actions>
      <AppRadio
        :model-value="metric"
        :options="metricOptions"
        @update:model-value="updateMetric"
      />
    </template>
    <div ref="chartElement" class="operating-dashboard-trend__chart" />
  </PageSection>
</template>

<style scoped>
.operating-dashboard-trend__chart {
  width: 100%;
  height: 190px;
}

@media (max-height: 760px) {
  .operating-dashboard-trend__chart {
    height: 160px;
  }
}
</style>
