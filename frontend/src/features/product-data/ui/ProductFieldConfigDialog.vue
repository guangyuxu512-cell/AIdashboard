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
  type ProductDisplayColumn,
  type ProductDisplayColumnId,
} from '../model/types'
import {
  productDisplayColumn,
  sanitizeProductDisplayColumns,
} from '../model/display-fields'

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
  error = ref<string | null>(null),
  dragging = ref<ProductDisplayColumnId | null>(null),
  dragTarget = ref<ProductDisplayColumnId | null>(null),
  dragAfter = ref(false),
  reorderStatus = ref('')

watch(
  () => props.show,
  (show) => {
    if (!show) return
    draft.value = normalizeProductColumns(props.columns)
    error.value = null
    dragging.value = null
    dragTarget.value = null
    reorderStatus.value = ''
  },
  { immediate: true },
)

const visibleCount = computed(() => draft.value.length)
const selectedColumns = computed(() =>
  draft.value
    .map((id) => productDisplayColumn(id))
    .filter((column): column is ProductDisplayColumn => Boolean(column)),
)

function toggle(id: ProductDisplayColumnId, checked: boolean) {
  if (checked) {
    if (!draft.value.includes(id))
      draft.value = sanitizeProductDisplayColumns([...draft.value, id])
    return
  }
  draft.value = draft.value.filter((column) => column !== id)
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
    : sanitizeProductDisplayColumns([...draft.value, ...ids])
}
function moveToIndex(id: ProductDisplayColumnId, index: number) {
  const current = draft.value.indexOf(id)
  if (current < 0) return
  const next = [...draft.value]
  next.splice(current, 1)
  const target = Math.max(0, Math.min(index, next.length))
  next.splice(target, 0, id)
  draft.value = next
  const label = productDisplayColumn(id)?.label ?? id
  reorderStatus.value = `${label}已移至第 ${target + 1} 项`
}
function moveBy(id: ProductDisplayColumnId, offset: -1 | 1) {
  const current = draft.value.indexOf(id)
  if (current < 0) return
  moveToIndex(id, current + offset)
}
function startDrag(id: ProductDisplayColumnId, event: DragEvent) {
  dragging.value = id
  dragTarget.value = null
  if (!event.dataTransfer) return
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', id)
}
function markDropTarget(id: ProductDisplayColumnId, event: DragEvent) {
  if (!dragging.value || dragging.value === id) return
  const bounds = (event.currentTarget as HTMLElement).getBoundingClientRect()
  dragTarget.value = id
  dragAfter.value = event.clientY >= bounds.top + bounds.height / 2
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
}
function dropColumn(targetId: ProductDisplayColumnId, event: DragEvent) {
  const source = dragging.value ?? event.dataTransfer?.getData('text/plain')
  if (!source || source === targetId) return endDrag()
  const sourceId = source as ProductDisplayColumnId
  if (!draft.value.includes(sourceId)) return endDrag()
  const next = draft.value.filter((id) => id !== sourceId)
  const target = next.indexOf(targetId)
  if (target < 0) return endDrag()
  next.splice(target + (dragAfter.value ? 1 : 0), 0, sourceId)
  draft.value = next
  const label = productDisplayColumn(sourceId)?.label ?? sourceId
  reorderStatus.value = `${label}已移至第 ${next.indexOf(sourceId) + 1} 项`
  endDrag()
}
function endDrag() {
  dragging.value = null
  dragTarget.value = null
  dragAfter.value = false
}
function reset() {
  draft.value = [...DEFAULT_PRODUCT_COLUMNS]
  error.value = null
}
function save() {
  const columns = sanitizeProductDisplayColumns(draft.value)
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
    size="lg"
    positive-text="保存"
    :positive-disabled="!draft.length"
    @confirm="save"
    @update:show="$emit('update:show', $event)"
  >
    <div class="product-fields">
      <div class="product-fields__summary">
        <span>商品信息 / ID · 固定左列；操作 · 固定右列</span>
        <span
          >已显示 {{ visibleCount }} /
          {{ PRODUCT_DISPLAY_COLUMNS.length }}</span
        >
      </div>
      <div class="product-fields__layout">
        <section class="product-fields__pane">
          <header class="product-fields__pane-header">
            <strong>可选字段</strong>
            <span>四组及组内顺序固定</span>
          </header>
          <div class="product-fields__pane-body">
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
                >
                  {{ groupSelected(group.id) ? '全不选' : '全选' }}
                </AppButton>
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
                    >
                      {{ column.label }}
                    </AppCheckbox>
                  </template>
                  {{
                    column.metricId ? productMetricTooltip(column.metricId) : ''
                  }}
                </NTooltip>
              </div>
            </section>
          </div>
        </section>
        <section class="product-fields__pane">
          <header class="product-fields__pane-header">
            <strong>显示中的字段</strong>
            <span>拖动排序 · × 移除</span>
          </header>
          <p id="product-field-reorder-help" class="product-fields__sr-only">
            拖动字段左侧手柄调整顺序；键盘用户可在手柄上使用上下、Home和End键。
          </p>
          <ol
            v-if="selectedColumns.length"
            class="product-fields__selected-list"
            aria-label="显示字段顺序"
            aria-describedby="product-field-reorder-help"
          >
            <li
              v-for="(column, index) in selectedColumns"
              :key="column.id"
              class="product-fields__selected-item"
              :class="{
                'product-fields__selected-item--dragging':
                  dragging === column.id,
                'product-fields__selected-item--drop-before':
                  dragTarget === column.id && !dragAfter,
                'product-fields__selected-item--drop-after':
                  dragTarget === column.id && dragAfter,
              }"
              :data-field-id="column.id"
              draggable="true"
              @dragstart="startDrag(column.id, $event)"
              @dragover.prevent="markDropTarget(column.id, $event)"
              @drop.prevent="dropColumn(column.id, $event)"
              @dragend="endDrag"
            >
              <button
                type="button"
                class="product-fields__drag-handle"
                :aria-label="`拖拽排序：${column.label}`"
                :title="`拖拽排序：${column.label}`"
                @keydown.up.prevent="moveBy(column.id, -1)"
                @keydown.down.prevent="moveBy(column.id, 1)"
                @keydown.home.prevent="moveToIndex(column.id, 0)"
                @keydown.end.prevent="moveToIndex(column.id, draft.length - 1)"
              >
                ⋮⋮
              </button>
              <span class="product-fields__selected-label">
                {{ index + 1 }}. {{ column.label }}
              </span>
              <AppButton
                size="small"
                tone="text"
                :aria-label="`移除${column.label}`"
                @click="toggle(column.id, false)"
              >
                ×
              </AppButton>
            </li>
          </ol>
          <div v-else class="product-fields__empty">至少选择一个字段</div>
          <p class="product-fields__sr-only" aria-live="polite">
            {{ reorderStatus }}
          </p>
        </section>
      </div>
      <NAlert v-if="error" type="error" :show-icon="false">{{ error }}</NAlert>
    </div>
    <template #footer-start>
      <AppButton @click="reset">恢复默认</AppButton>
    </template>
  </AppDialog>
</template>

<style scoped>
.product-fields {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.product-fields__summary,
.product-fields__pane-header,
.product-fields__group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}
.product-fields__summary,
.product-fields__pane-header span {
  color: var(--text-secondary);
}
.product-fields__layout {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(250px, 0.85fr);
  gap: var(--space-4);
  min-width: 0;
}
.product-fields__pane {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 280px;
  max-height: min(460px, calc(100dvh - 280px));
  overflow: hidden;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  background: var(--bg-surface);
}
.product-fields__pane-header {
  flex: 0 0 auto;
  padding: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
  font-size: var(--font-size-secondary);
}
.product-fields__pane-body,
.product-fields__selected-list {
  min-height: 0;
  overflow: auto;
}
.product-fields__pane-body {
  padding: var(--space-3);
}
.product-fields__group {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
}
.product-fields__group + .product-fields__group {
  margin-top: var(--space-4);
}
.product-fields__group-header {
  font-weight: var(--font-weight-medium);
}
.product-fields__options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-2) var(--space-4);
}
.product-fields__options :deep(.app-checkbox) {
  min-width: 0;
}
.product-fields__selected-list {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: var(--space-2);
  margin: 0;
  padding: var(--space-3);
  list-style: none;
}
.product-fields__selected-item {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr) 30px;
  align-items: center;
  gap: var(--space-2);
  min-height: var(--control-height-default);
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  background: var(--bg-surface-solid);
}
.product-fields__selected-item--dragging {
  opacity: 0.55;
}
.product-fields__selected-item--drop-before {
  box-shadow: inset 0 2px 0 var(--color-primary);
}
.product-fields__selected-item--drop-after {
  box-shadow: inset 0 -2px 0 var(--color-primary);
}
.product-fields__drag-handle {
  width: 30px;
  height: 30px;
  padding: 0;
  border: 0;
  border-radius: var(--radius-control);
  color: var(--text-secondary);
  background: transparent;
  cursor: grab;
}
.product-fields__drag-handle:hover,
.product-fields__drag-handle:focus-visible {
  color: var(--text-primary);
  background: var(--bg-surface-hover);
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}
.product-fields__drag-handle:active {
  cursor: grabbing;
}
.product-fields__selected-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.product-fields__empty {
  display: grid;
  flex: 1 1 auto;
  place-items: center;
  min-height: 160px;
  color: var(--text-secondary);
}
.product-fields__sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
@media (max-width: 640px) {
  .product-fields__layout {
    grid-template-columns: minmax(0, 1fr);
  }
  .product-fields__pane {
    max-height: 320px;
  }
}
@media (max-width: 480px) {
  .product-fields__options {
    grid-template-columns: minmax(0, 1fr);
  }
  .product-fields__summary {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
