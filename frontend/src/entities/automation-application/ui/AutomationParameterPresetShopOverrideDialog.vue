<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import FormDialog from '@/shared/components/FormDialog.vue'
import { AppButton, AppInput } from '@/shared/ui'

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

const query = ref('')
const draftOverrides = ref<Record<string, unknown>>({})
const fields = computed(() => mapAutomationParameterFields(props.schema))
const filteredSchema = computed(() => {
  const value = query.value.trim().toLocaleLowerCase()
  if (!value) return props.schema
  return {
    fields: props.schema.fields.filter((field) =>
      `${field.label} ${field.name}`.toLocaleLowerCase().includes(value),
    ),
  }
})
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
    query.value = ''
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
    :submit-disabled="disabled"
    @update:show="$emit('update:show', $event)"
    @submit="confirm"
  >
    <p class="shop-override-dialog__hint">
      公共值来自当前配置；只保存本店与公共值不同的字段。确定后仅回填主编辑器草稿。
    </p>
    <div v-if="fields.length" class="shop-override-dialog__common-values">
      <div v-for="field in fields" :key="field.name">
        <strong>{{ field.label }}</strong>
        <span>公共值：{{ valueText(commonParameters[field.name]) }}</span>
      </div>
    </div>
    <AppInput
      v-if="fields.length"
      v-model="query"
      clearable
      placeholder="搜索参数"
    />
    <div v-if="fields.length" class="shop-override-dialog__parameter-viewport">
      <AutomationParameterFields
        :model-value="effectiveParameters"
        :schema="filteredSchema"
        :disabled="disabled"
        preserve-empty-string
        @update:model-value="updateParameters"
      />
    </div>
    <div
      v-if="Object.keys(draftOverrides).length"
      class="shop-override-dialog__inheritance"
    >
      <AppButton
        v-for="name in Object.keys(draftOverrides).filter(
          (name) => !unknownOverrideNames.includes(name),
        )"
        :key="name"
        tone="text"
        @click="restoreInheritance(name)"
      >
        恢复公共值 · {{ fields.find((field) => field.name === name)?.label ?? name }}
      </AppButton>
    </div>
    <section v-if="unknownOverrideNames.length" class="shop-override-dialog__legacy">
      <h3>待修正字段</h3>
      <p>这些旧值已不在当前应用字段定义中；移除只影响本店差异，不会删除应用字段定义。</p>
      <div v-for="name in unknownOverrideNames" :key="name">
        <span>{{ name }}：{{ valueText(draftOverrides[name]) }}</span>
        <AppButton tone="danger" @click="restoreInheritance(name)">移除旧值</AppButton>
      </div>
    </section>
  </FormDialog>
</template>

<style scoped>
.shop-override-dialog__hint,
.shop-override-dialog__legacy p {
  margin: 0;
  color: var(--text-secondary);
}

.shop-override-dialog__common-values,
.shop-override-dialog__inheritance,
.shop-override-dialog__legacy {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.shop-override-dialog__common-values {
  max-height: 128px;
  overflow-y: auto;
  padding: var(--space-2);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
}

.shop-override-dialog__common-values div,
.shop-override-dialog__legacy > div {
  display: flex;
  min-width: 0;
  justify-content: space-between;
  gap: var(--space-3);
}

.shop-override-dialog__common-values span {
  overflow: hidden;
  color: var(--text-secondary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.shop-override-dialog__parameter-viewport {
  max-height: 280px;
  overflow-y: auto;
  padding-right: var(--space-2);
}

.shop-override-dialog__inheritance {
  flex-direction: row;
  flex-wrap: wrap;
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
</style>
