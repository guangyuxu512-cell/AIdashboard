<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { NAlert, NTooltip } from 'naive-ui'
import { AppButton, AppCheckbox, AppDialog } from '@/shared/ui'
import {
  normalizeProductColumns,
  saveProductColumns,
} from '../model/column-preferences'
import { productMetricTooltip } from '../model/metrics'
import { PRODUCT_METRIC_TOOLTIP_STYLE } from './metric-tooltip'
import {
  DEFAULT_PRODUCT_COLUMNS,
  PRODUCT_DATA_FIELD_GROUPS,
  PRODUCT_DISPLAY_COLUMNS,
  type ProductDisplayColumnId,
} from '../model/types'
import { orderProductDisplayColumns } from '../model/display-fields'

const props = defineProps<{
  show: boolean
  columns: ProductDisplayColumnId[]
  userId: string | null
}>()
const emit = defineEmits<{
  'update:show': [show: boolean]
  saved: [columns: ProductDisplayColumnId[]]
}>()
const draft = ref<ProductDisplayColumnId[]>([]),
  error = ref<string | null>(null)
watch(
  () => props.show,
  (show) => {
    if (!show) return
    draft.value = normalizeProductColumns(props.columns)
    error.value = null
  },
  { immediate: true },
)
const visibleCount = computed(() => draft.value.length)
function toggle(id: ProductDisplayColumnId, checked: boolean) {
  draft.value = checked
    ? [...draft.value, id]
    : draft.value.filter((column) => column !== id)
}
function groupColumns(group: (typeof PRODUCT_DATA_FIELD_GROUPS)[number]['id']) {
  return PRODUCT_DISPLAY_COLUMNS.filter((column) => column.group === group)
}
function groupSelected(
  group: (typeof PRODUCT_DATA_FIELD_GROUPS)[number]['id'],
) {
  const columns = groupColumns(group)
  return columns.every(({ id }) => draft.value.includes(id))
}
function toggleGroup(group: (typeof PRODUCT_DATA_FIELD_GROUPS)[number]['id']) {
  const ids = groupColumns(group).map(({ id }) => id)
  draft.value = groupSelected(group)
    ? draft.value.filter((id) => !ids.includes(id))
    : [...new Set([...draft.value, ...ids])]
}
function reset() {
  draft.value = [...DEFAULT_PRODUCT_COLUMNS]
  error.value = null
}
function save() {
  const columns = orderProductDisplayColumns(draft.value)
  try {
    saveProductColumns(props.userId, columns)
    emit('saved', columns)
    emit('update:show', false)
  } catch (cause) {
    error.value =
      cause instanceof Error && cause.message.includes('至少')
        ? cause.message
        : '个人字段配置保存失败，请重试'
  }
}
</script>

<template>
  <AppDialog
    :show="show"
    title="字段配置"
    positive-text="保存"
    :positive-disabled="!draft.length"
    @confirm="save"
    @update:show="$emit('update:show', $event)"
  >
    <div class="product-fields">
      <div class="product-fields__summary">
        <span>可选字段</span>
        <span
          >已显示 {{ visibleCount }} /
          {{ PRODUCT_DISPLAY_COLUMNS.length }}</span
        >
      </div>
      <div class="product-fields__fixed">
        商品信息 / ID · 固定左列；操作 · 固定右列
      </div>
      <section
        v-for="group in PRODUCT_DATA_FIELD_GROUPS"
        :key="group.id"
        class="product-fields__group"
      >
        <header class="product-fields__group-header">
          <span>{{ group.label }}</span>
          <AppButton
            v-if="group.id !== 'basic'"
            size="small"
            tone="text"
            @click="toggleGroup(group.id)"
            >{{ groupSelected(group.id) ? '全不选' : '全选' }}</AppButton
          >
        </header>
        <div class="product-fields__options">
          <NTooltip
            v-for="column in groupColumns(group.id)"
            :key="column.id"
            :disabled="!column.metricId"
            :content-style="PRODUCT_METRIC_TOOLTIP_STYLE"
          >
            <template #trigger>
              <AppCheckbox
                :model-value="draft.includes(column.id)"
                @update:model-value="toggle(column.id, $event)"
                >{{ column.label }}</AppCheckbox
              >
            </template>
            {{ column.metricId ? productMetricTooltip(column.metricId) : '' }}
          </NTooltip>
        </div>
      </section>
      <NAlert v-if="error" type="error" :show-icon="false">{{ error }}</NAlert>
    </div>
    <template #footer-start
      ><AppButton @click="reset">恢复默认</AppButton></template
    >
  </AppDialog>
</template>

<style scoped>
.product-fields {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.product-fields__summary,
.product-fields__group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}
.product-fields__summary span:last-child,
.product-fields__fixed {
  color: var(--text-secondary);
}
.product-fields__fixed {
  margin-top: calc(var(--space-2) * -1);
}
.product-fields__group {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.product-fields__group-header {
  font-weight: var(--font-weight-medium);
}
.product-fields__options {
  display: grid;
  grid-template-columns: repeat(
    auto-fit,
    minmax(min(100%, var(--field-width-sm)), 1fr)
  );
  gap: var(--space-2) var(--space-4);
}
.product-fields__options :deep(.app-checkbox) {
  min-width: 0;
}
</style>
