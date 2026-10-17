<script setup lang="ts">
import { computed } from 'vue'
import { NText, NTooltip } from 'naive-ui'
import { FilterField } from '@/shared/components'
import { AppNumberInput, AppSelect, type AppOptionValue } from '@/shared/ui'
import { productMetricTooltip } from '../model/metrics'
import { PRODUCT_METRIC_TOOLTIP_STYLE } from './metric-tooltip'
import {
  PRODUCT_RANGE_FILTERS,
  productRangeLabel,
  productRangeOptions,
  selectProductRange,
  type ProductRangeChoice,
  type ProductRangeDraft,
  type ProductRangeFilterId,
} from '../model/metric-ranges'

const props = defineProps<{
  metricId: ProductRangeFilterId
  modelValue: ProductRangeDraft
  disabled: boolean
  error?: string
}>()
const emit = defineEmits<{ 'update:modelValue': [value: ProductRangeDraft] }>()
const label = computed(() => productRangeLabel(props.metricId))
const percent = computed(
  () =>
    PRODUCT_RANGE_FILTERS.find((field) => field.id === props.metricId)!.percent,
)
function select(value: AppOptionValue | null) {
  emit(
    'update:modelValue',
    selectProductRange(value as ProductRangeChoice | null, props.modelValue),
  )
}
</script>

<template>
  <FilterField
    class="product-range-field"
    :data-metric-filter="metricId"
    width="sm"
  >
    <NTooltip :content-style="PRODUCT_METRIC_TOOLTIP_STYLE">
      <template #trigger
        ><span>{{ label }}{{ percent ? '（%）' : '' }}</span></template
      >
      {{ productMetricTooltip(metricId) }}
    </NTooltip>
    <AppSelect
      :model-value="modelValue.choice"
      :options="productRangeOptions(metricId)"
      :aria-label="label + '区间'"
      :disabled="disabled"
      clearable
      @update:model-value="select"
    />
    <div
      v-if="modelValue.choice === 'custom'"
      class="product-range-field__bounds"
    >
      <AppNumberInput
        :model-value="modelValue.min"
        :aria-label="label + '下限'"
        :input-props="{ 'aria-label': label + '下限' }"
        placeholder="含下限"
        :disabled="disabled"
        clearable
        @update:model-value="
          $emit('update:modelValue', { ...modelValue, min: $event })
        "
      />
      <AppNumberInput
        :model-value="modelValue.max"
        :aria-label="label + '上限'"
        :input-props="{ 'aria-label': label + '上限' }"
        placeholder="不含上限"
        :disabled="disabled"
        clearable
        @update:model-value="
          $emit('update:modelValue', { ...modelValue, max: $event })
        "
      />
    </div>
    <NText v-if="error" type="error" role="alert">{{ error }}</NText>
  </FilterField>
</template>

<style scoped>
.product-range-field {
  gap: var(--space-1);
  max-width: 100%;
}
.product-range-field__bounds {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--space-1);
}
</style>
