<script setup lang="ts">
import dayjs from 'dayjs'
import { NDescriptions, NDescriptionsItem, NTooltip } from 'naive-ui'
import { ProductInfoCell } from '@/entities/product'
import { DetailDrawer } from '@/shared/components'
import { AppButton } from '@/shared/ui'
import {
  formatProductMetric,
  PRODUCT_METRIC_STATE_LABELS,
} from '../model/query'
import { PRODUCT_METRICS, type ProductDataRow } from '../model/types'
import { productMetricTooltip } from '../model/metrics'
import { PRODUCT_METRIC_TOOLTIP_STYLE } from './metric-tooltip'
defineProps<{ show: boolean; row: ProductDataRow | null }>()
defineEmits<{ 'update:show': [show: boolean] }>()
</script>

<template>
  <DetailDrawer
    :show="show"
    title="商品详情"
    @update:show="$emit('update:show', $event)"
  >
    <div v-if="row" class="product-data-detail">
      <ProductInfoCell
        :product-id="row.productId"
        :title="row.title"
        :image-url="row.imageUrl"
      />
      <NDescriptions :column="1" label-placement="left">
        <NDescriptionsItem label="店铺">{{ row.shopName }}</NDescriptionsItem>
        <NDescriptionsItem label="商品分组">{{
          row.groupName ?? '未分组'
        }}</NDescriptionsItem>
        <NDescriptionsItem label="统计日期"
          >{{ row.period.startDate }} ～
          {{ row.period.endDate }}</NDescriptionsItem
        >
        <NDescriptionsItem label="数据时间">{{
          dayjs(row.retrievedAt).format('YYYY-MM-DD HH:mm')
        }}</NDescriptionsItem>
        <NDescriptionsItem v-for="metric in PRODUCT_METRICS" :key="metric.id">
          <template #label>
            <NTooltip :content-style="PRODUCT_METRIC_TOOLTIP_STYLE"
              ><template #trigger
                ><span>{{ metric.label }}</span></template
              >{{ productMetricTooltip(metric.id) }}</NTooltip
            >
          </template>
          {{ formatProductMetric(row.metrics[metric.id]) }}
          <span
            v-if="row.metrics[metric.id].state !== 'available'"
            class="product-data-detail__missing"
          >
            ·
            {{
              PRODUCT_METRIC_STATE_LABELS[row.metrics[metric.id].state]
            }}</span
          >
        </NDescriptionsItem>
      </NDescriptions>
    </div>
    <template #footer
      ><AppButton @click="$emit('update:show', false)"
        >关闭</AppButton
      ></template
    >
  </DetailDrawer>
</template>

<style scoped>
.product-data-detail {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}
.product-data-detail__missing {
  color: var(--text-secondary);
}
</style>
