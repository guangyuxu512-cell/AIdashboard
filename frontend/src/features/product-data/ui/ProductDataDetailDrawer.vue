<script setup lang="ts">
import { NDescriptions, NDescriptionsItem, NTooltip } from 'naive-ui'
import { ProductInfoCell } from '@/entities/product'
import { DetailDrawer } from '@/shared/components'
import { AppButton } from '@/shared/ui'
import {
  formatProductMetric,
  PRODUCT_METRIC_STATE_LABELS,
} from '../model/query'
import {
  PRODUCT_DATA_FIELD_GROUPS,
  PRODUCT_DISPLAY_COLUMNS,
  type ProductDataRow,
  type ProductDisplayColumn,
} from '../model/types'
import { productMetricTooltip } from '../model/metrics'
import { productDisplayMetricId } from '../model/display-fields'
import { PRODUCT_METRIC_TOOLTIP_STYLE } from './metric-tooltip'
defineProps<{ show: boolean; row: ProductDataRow | null }>()
defineEmits<{ 'update:show': [show: boolean] }>()

function groupColumns(group: (typeof PRODUCT_DATA_FIELD_GROUPS)[number]['id']) {
  return PRODUCT_DISPLAY_COLUMNS.filter((column) => column.group === group)
}
function displayValue(row: ProductDataRow, column: ProductDisplayColumn) {
  if (column.id === 'shop') return row.shopName
  const metricId = productDisplayMetricId(column.id)
  return metricId ? formatProductMetric(row.metrics[metricId]) : '—'
}
function displayState(row: ProductDataRow, column: ProductDisplayColumn) {
  const metricId = productDisplayMetricId(column.id)
  if (!metricId || row.metrics[metricId].state === 'available') return null
  return PRODUCT_METRIC_STATE_LABELS[row.metrics[metricId].state]
}
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
      <section
        v-for="group in PRODUCT_DATA_FIELD_GROUPS"
        :key="group.id"
        class="product-data-detail__group"
      >
        <h3 class="product-data-detail__group-title">{{ group.label }}</h3>
        <NDescriptions
          :column="1"
          bordered
          label-placement="left"
          label-align="left"
          :label-style="{ width: 'var(--field-width-sm)' }"
        >
          <NDescriptionsItem
            v-for="column in groupColumns(group.id)"
            :key="column.id"
          >
            <template #label>
              <NTooltip
                :disabled="!column.metricId"
                :content-style="PRODUCT_METRIC_TOOLTIP_STYLE"
              >
                <template #trigger
                  ><span>{{ column.label }}</span></template
                >
                {{
                  column.metricId ? productMetricTooltip(column.metricId) : ''
                }}
              </NTooltip>
            </template>
            <span class="product-data-detail__value">
              {{ displayValue(row, column) }}
              <span
                v-if="displayState(row, column)"
                class="product-data-detail__missing"
              >
                · {{ displayState(row, column) }}
              </span>
            </span>
          </NDescriptionsItem>
        </NDescriptions>
      </section>
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
  min-width: 0;
}
.product-data-detail__group {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
}
.product-data-detail__group-title {
  margin: 0;
  color: var(--text-primary);
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-semibold);
}
.product-data-detail__value {
  overflow-wrap: anywhere;
}
.product-data-detail__missing {
  color: var(--text-secondary);
}
</style>
