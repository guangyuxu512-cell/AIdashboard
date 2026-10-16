<script setup lang="ts">
import { ref, watch } from 'vue'
import { NAlert, NTooltip } from 'naive-ui'
import { AppButton, AppCheckbox, AppDialog } from '@/shared/ui'
import {
  normalizeProductColumns,
  saveProductColumns,
} from '../model/column-preferences'
import { productMetricTooltip } from '../model/metrics'
import {
  DEFAULT_PRODUCT_COLUMNS,
  PRODUCT_COLUMNS,
  type ProductColumnId,
} from '../model/types'

const props = defineProps<{
  show: boolean
  columns: ProductColumnId[]
  userId: string | null
}>()
const emit = defineEmits<{
  'update:show': [show: boolean]
  saved: [columns: ProductColumnId[]]
}>()
const draft = ref<ProductColumnId[]>([]),
  order = ref<ProductColumnId[]>([]),
  error = ref<string | null>(null)
watch(
  () => props.show,
  (show) => {
    if (!show) return
    draft.value = normalizeProductColumns(props.columns)
    order.value = [
      ...draft.value,
      ...PRODUCT_COLUMNS.map((column) => column.id).filter(
        (id) => !draft.value.includes(id),
      ),
    ]
    error.value = null
  },
  { immediate: true },
)
function toggle(id: ProductColumnId, checked: boolean) {
  draft.value = checked
    ? [...draft.value, id]
    : draft.value.filter((column) => column !== id)
}
function move(index: number, direction: number) {
  const next = [...order.value],
    target = index + direction
  if (target < 0 || target >= next.length) return
  ;[next[index], next[target]] = [next[target]!, next[index]!]
  order.value = next
}
function reset() {
  draft.value = [...DEFAULT_PRODUCT_COLUMNS]
  order.value = [
    ...DEFAULT_PRODUCT_COLUMNS,
    ...PRODUCT_COLUMNS.map((column) => column.id).filter(
      (id) => !DEFAULT_PRODUCT_COLUMNS.includes(id),
    ),
  ]
  error.value = null
}
function save() {
  const columns = order.value.filter((id) => draft.value.includes(id))
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
      <div class="product-fields__fixed">商品信息 · 固定显示</div>
      <div v-for="(id, index) in order" :key="id" class="product-fields__row">
        <NTooltip :disabled="!productMetricTooltip(id)">
          <template #trigger>
            <AppCheckbox
              :model-value="draft.includes(id)"
              @update:model-value="toggle(id, $event)"
              >{{
                PRODUCT_COLUMNS.find((column) => column.id === id)?.label
              }}</AppCheckbox
            >
          </template>
          {{ productMetricTooltip(id) }}
        </NTooltip>
        <div class="product-fields__actions">
          <AppButton
            size="small"
            tone="text"
            :disabled="index === 0"
            :aria-label="
              '上移' + PRODUCT_COLUMNS.find((column) => column.id === id)?.label
            "
            @click="move(index, -1)"
            >上移</AppButton
          >
          <AppButton
            size="small"
            tone="text"
            :disabled="index === order.length - 1"
            :aria-label="
              '下移' + PRODUCT_COLUMNS.find((column) => column.id === id)?.label
            "
            @click="move(index, 1)"
            >下移</AppButton
          >
        </div>
      </div>
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
  gap: var(--space-2);
}
.product-fields__fixed {
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}
.product-fields__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}
.product-fields__actions {
  display: flex;
  gap: var(--space-1);
}
</style>
