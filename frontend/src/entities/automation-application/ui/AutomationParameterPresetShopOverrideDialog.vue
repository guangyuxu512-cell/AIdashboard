<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import FormDialog from '@/shared/components/FormDialog.vue'
import { AppButton } from '@/shared/ui'

import type { AutomationInputSchemaDto } from '../api/contracts'
import { mapAutomationParameterFields } from '../model/parameters'
import AutomationParameterFields from './AutomationParameterFields.vue'

const props = withDefaults(
  defineProps<{
    show: boolean
    shopId: string | null
    shopName: string
    schema: AutomationInputSchemaDto
    commonParameters: Record<string, unknown>
    shopOverrides: Record<string, unknown>
    disabled?: boolean
  }>(),
  { disabled: false },
)

const emit = defineEmits<{
  'update:show': [value: boolean]
  confirm: [overrides: Record<string, unknown>]
}>()

const draftOverrides = ref<Record<string, unknown>>({})
const fields = computed(() => mapAutomationParameterFields(props.schema))
const effectiveParameters = computed(() => ({
  ...props.commonParameters,
  ...draftOverrides.value,
}))
const unknownOverrideNames = computed(() => {
  const known = new Set(fields.value.map((field) => field.name))
  return Object.keys(draftOverrides.value).filter((name) => !known.has(name))
})

watch(
  [() => props.show, () => props.shopId],
  ([show]) => {
    if (!show) return
    draftOverrides.value = { ...props.shopOverrides }
  },
  { immediate: true },
)

function updateParameters(next: Record<string, unknown>): void {
  const overrides = { ...draftOverrides.value }
  for (const field of fields.value) {
    const name = field.name
    if (!Object.prototype.hasOwnProperty.call(next, name)) {
      delete overrides[name]
      continue
    }
    if (next[name] === props.commonParameters[name]) delete overrides[name]
    else overrides[name] = next[name]
  }
  draftOverrides.value = overrides
}

function restoreInheritance(name: string): void {
  const overrides = { ...draftOverrides.value }
  delete overrides[name]
  draftOverrides.value = overrides
}

function valueText(value: unknown): string {
  if (value === '') return '（空）'
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function confirm(): void {
  emit('confirm', { ...draftOverrides.value })
  emit('update:show', false)
}
</script>

<template>
  <FormDialog
    :show="show"
    :title="`店铺差异 · ${shopName}`"
    size="md"
    submit-text="确定"
    :submit-disabled="disabled"
    @update:show="$emit('update:show', $event)"
    @submit="confirm"
  >
    <div v-if="fields.length" class="shop-override-dialog__parameter-viewport">
      <div class="shop-override-dialog__column-headings" aria-hidden="true">
        <span>字段</span>
        <span>公共值</span>
        <span>本店值</span>
        <span>恢复</span>
      </div>
      <AutomationParameterFields
        :model-value="effectiveParameters"
        :schema="schema"
        :disabled="disabled"
        :reference-values="commonParameters"
        layout="comparison"
        preserve-empty-string
        show-restore
        @update:model-value="updateParameters"
        @restore="restoreInheritance"
      />
    </div>
    <section v-if="unknownOverrideNames.length" class="shop-override-dialog__legacy">
      <h3>待修正字段</h3>
      <p>这些旧值已不在当前应用字段定义中；移除只影响本店差异，不会删除应用字段定义。</p>
      <div v-for="name in unknownOverrideNames" :key="name">
        <span>{{ name }}：{{ valueText(draftOverrides[name]) }}</span>
        <AppButton tone="text" @click="restoreInheritance(name)">移除旧值</AppButton>
      </div>
    </section>
  </FormDialog>
</template>

<style scoped>
.shop-override-dialog__legacy p {
  margin: 0;
  color: var(--text-secondary);
}

.shop-override-dialog__legacy {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.shop-override-dialog__legacy > div {
  display: flex;
  min-width: 0;
  justify-content: space-between;
  gap: var(--space-3);
}

.shop-override-dialog__parameter-viewport {
  max-height: 280px;
  overflow-y: auto;
  padding-right: var(--space-1);
}

.shop-override-dialog__column-headings {
  display: grid;
  margin-bottom: var(--space-2);
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
  grid-template-columns: var(--field-width-sm) minmax(0, 0.75fr) minmax(0, 1fr) auto;
  gap: var(--space-2);
}

.shop-override-dialog__column-headings span:last-child {
  min-width: 32px;
  text-align: center;
}

.shop-override-dialog__legacy {
  padding: var(--space-3);
  border: 1px solid var(--color-warning);
  border-radius: var(--radius-card);
}

.shop-override-dialog__legacy h3 {
  margin: 0;
  font-size: var(--font-size-body);
}

@media (max-width: 640px) {
  .shop-override-dialog__column-headings {
    grid-template-columns: var(--field-width-xs) minmax(0, 1fr) minmax(0, 1fr) auto;
  }
}
</style>
