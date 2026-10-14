<script setup lang="ts">
import { computed, ref } from 'vue'
import dayjs from 'dayjs'
import { NAlert } from 'naive-ui'
import { useShopSelectionOptionsQuery } from '@/entities/shop/api/shop-queries'
import { FilterBar, FilterField } from '@/shared/components'
import {
  AppButton,
  AppDatePicker,
  AppInput,
  AppNumberInput,
  AppRadio,
  AppSelect,
  type AppDateValue,
  type AppOptionValue,
} from '@/shared/ui'
import type { ProductDataFilters, ProductGroup } from '../model/types'

const props = defineProps<{
  modelValue: ProductDataFilters
  groups: ProductGroup[]
  enabled: boolean
  loading: boolean
  groupsLoading?: boolean
  groupsError?: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [value: ProductDataFilters]
  query: []
  reset: []
  fields: []
  retryGroups: []
}>()
const more = ref(false)
const shops = useShopSelectionOptionsQuery()
const dateOptions = [
  { label: '昨日', value: 'yesterday' },
  { label: '近7天', value: 'last7Days' },
  { label: '近30天', value: 'last30Days' },
  { label: '自定义', value: 'custom' },
]
const groupOptions = computed(() => [
  { label: '未分组', value: 'ungrouped' },
  ...props.groups.map((group) => ({ label: group.name, value: group.id })),
])
function update<K extends keyof ProductDataFilters>(
  key: K,
  value: ProductDataFilters[K],
) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}
function selectDate(value: AppOptionValue) {
  const datePreset = value as ProductDataFilters['datePreset']
  const yesterday = dayjs().startOf('day').subtract(1, 'day').valueOf()
  emit('update:modelValue', {
    ...props.modelValue,
    datePreset,
    customDateRange:
      datePreset === 'custom'
        ? (props.modelValue.customDateRange ?? [yesterday, yesterday])
        : props.modelValue.customDateRange,
  })
}
function dateRange(value: AppDateValue) {
  update('customDateRange', Array.isArray(value) ? value : null)
}
function select<K extends 'groupId' | 'selling' | 'carrier'>(
  key: K,
  value: AppOptionValue | null,
) {
  update(key, value === null ? null : (String(value) as ProductDataFilters[K]))
}
</script>

<template>
  <div class="product-data-filters">
    <FilterBar>
      <FilterField width="sm">
        <AppSelect
          :model-value="modelValue.shopId"
          :options="shops.data.value ?? []"
          :loading="shops.isFetching.value"
          filterable
          clearable
          :disabled="!enabled"
          placeholder="全部店铺"
          @update:model-value="
            update('shopId', $event === null ? null : String($event))
          "
        />
      </FilterField>
      <FilterField width="sm"
        ><AppInput
          :model-value="modelValue.productId"
          clearable
          aria-label="商品ID"
          placeholder="商品ID"
          :disabled="!enabled"
          @update:model-value="update('productId', $event)"
      /></FilterField>
      <FilterField width="md"
        ><AppInput
          :model-value="modelValue.productName"
          clearable
          aria-label="商品名称"
          placeholder="商品名称"
          :disabled="!enabled"
          @update:model-value="update('productName', $event)"
      /></FilterField>
      <FilterField width="sm"
        ><AppSelect
          :model-value="modelValue.groupId"
          :options="groupOptions"
          clearable
          placeholder="商品分组"
          :disabled="
            !enabled || !modelValue.shopId || groupsError || groupsLoading
          "
          :loading="groupsLoading"
          @update:model-value="select('groupId', $event)"
      /></FilterField>
      <FilterField width="xs"
        ><AppSelect
          :model-value="modelValue.selling"
          clearable
          placeholder="售卖状态"
          :disabled="!enabled"
          :options="[
            { label: '在售', value: 'on-sale' },
            { label: '停售', value: 'off-sale' },
          ]"
          @update:model-value="select('selling', $event)"
      /></FilterField>
      <FilterField width="xs"
        ><AppSelect
          :model-value="modelValue.carrier"
          clearable
          placeholder="商品载体"
          :disabled="!enabled"
          :options="[
            { label: '商品卡', value: 'card' },
            { label: '短视频', value: 'video' },
            { label: '直播', value: 'live' },
          ]"
          @update:model-value="select('carrier', $event)"
      /></FilterField>
      <AppButton
        tone="text"
        :disabled="!enabled"
        :aria-expanded="more"
        @click="more = !more"
        >更多筛选</AppButton
      >
    </FilterBar>
    <NAlert v-if="groupsError" type="error" :show-icon="false">
      <div class="product-data-filters__feedback">
        <span>分组读取失败</span>
        <AppButton tone="text" @click="$emit('retryGroups')"
          >重新加载分组</AppButton
        >
      </div>
    </NAlert>
    <div v-if="more" class="product-data-filters__more">
      <FilterField width="sm"
        ><AppNumberInput
          :model-value="modelValue.minExposure"
          :min="0"
          clearable
          placeholder="最低曝光人数"
          @update:model-value="update('minExposure', $event)"
      /></FilterField>
      <FilterField width="sm"
        ><AppNumberInput
          :model-value="modelValue.minOrders"
          :min="0"
          clearable
          placeholder="最低成交订单数"
          @update:model-value="update('minOrders', $event)"
      /></FilterField>
    </div>
    <FilterBar>
      <AppRadio
        :model-value="modelValue.datePreset"
        :options="dateOptions"
        :disabled="!enabled"
        @update:model-value="selectDate"
      />
      <AppDatePicker
        v-if="modelValue.datePreset === 'custom'"
        :model-value="modelValue.customDateRange"
        type="daterange"
        :disabled="!enabled"
        :clearable="false"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        :is-date-disabled="
          (timestamp) =>
            dayjs(timestamp).startOf('day').valueOf() >=
            dayjs().startOf('day').valueOf()
        "
        @update:model-value="dateRange"
      />
      <template #actions>
        <AppButton
          tone="primary"
          :loading="loading"
          :disabled="!enabled || loading"
          @click="$emit('query')"
          >查询</AppButton
        >
        <AppButton :disabled="!enabled || loading" @click="$emit('reset')"
          >重置</AppButton
        >
        <AppButton @click="$emit('fields')">字段配置</AppButton>
      </template>
    </FilterBar>
  </div>
</template>

<style scoped>
.product-data-filters {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.product-data-filters__more {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}
.product-data-filters__feedback {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}
@media (max-width: 1200px) {
  .product-data-filters :deep(.filter-bar) {
    flex-wrap: wrap;
  }
  .product-data-filters :deep(.filter-bar__toolbar) {
    margin-left: auto;
  }
}
</style>
