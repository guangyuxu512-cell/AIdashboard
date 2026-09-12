<script setup lang="ts">
import { NFormItem } from 'naive-ui'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { AppButton, AppSelect } from '@/shared/ui'
import type { ShopSelectOption } from '@/entities/shop'

import type { AutomationInputSchemaDto } from '../api/contracts'
import { useAutomationParameterPresetsQuery } from '../api/queries'
import { mapAutomationParameterFields } from '../model/parameters'

const props = defineProps<{
  appId: string | null
  shopIds: string[]
  shopOptions: ShopSelectOption[]
  schema: AutomationInputSchemaDto
  modelValue: string | null
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string | null]
}>()

const router = useRouter()
const previewOpen = ref(false)
const presetsQuery = useAutomationParameterPresetsQuery(() => props.appId)
const presets = computed(() => presetsQuery.data.value ?? [])
const selectedPreset = computed(
  () =>
    presets.value.find((preset) => preset.preset_id === props.modelValue) ??
    null,
)
const presetOptions = computed(() =>
  presets.value.map((preset) => ({
    label: preset.name,
    value: preset.preset_id,
  })),
)
const preview = computed(() => {
  const preset = selectedPreset.value
  if (!preset) return []
  const selectedShopIds = props.shopIds.length ? props.shopIds : []
  return selectedShopIds.map((shopId) => ({
    shopId,
    shopName:
      props.shopOptions.find((option) => option.value === shopId)?.label ??
      shopId,
    parameters: {
      ...preset.common_parameters,
      ...(preset.shop_overrides[shopId] ?? {}),
    },
  }))
})
const overrideShopCount = computed(
  () =>
    preview.value.filter(
      (item) =>
        Object.keys(selectedPreset.value?.shop_overrides[item.shopId] ?? {})
          .length,
    ).length,
)
const parameterLabels = computed(
  () =>
    new Map(
      mapAutomationParameterFields(props.schema).map((field) => [
        field.name,
        field.label,
      ]),
    ),
)

function change(value: unknown): void {
  previewOpen.value = false
  emit('update:modelValue', typeof value === 'string' ? value : null)
}

function describeShop(item: (typeof preview.value)[number]): string {
  const overrides = selectedPreset.value?.shop_overrides[item.shopId] ?? {}
  const names = Object.keys(overrides)
  return names.length ? `已单独设置：${names.join('、')}` : '使用公共参数'
}

function parameterEntries(
  item: (typeof preview.value)[number],
): Array<[string, unknown]> {
  const positions = new Map(
    mapAutomationParameterFields(props.schema).map((field, index) => [
      field.name,
      index,
    ]),
  )
  return Object.entries(item.parameters).sort(
    ([left], [right]) =>
      (positions.get(left) ?? Number.MAX_SAFE_INTEGER) -
      (positions.get(right) ?? Number.MAX_SAFE_INTEGER),
  )
}

function parameterLabel(name: string): string {
  return parameterLabels.value.get(name) ?? name
}

function parameterValue(value: unknown): string {
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (value === '') return '（空）'
  if (value === null || value === undefined) return '—'
  return String(value)
}

function openPresetManagement(): void {
  void router.push({
    path: '/parameter-presets',
    query: props.appId ? { app_id: props.appId } : undefined,
  })
}
</script>

<template>
  <NFormItem label="参数预设">
    <div class="preset-selector-content">
      <div class="preset-selector">
        <AppSelect
          :model-value="modelValue"
          :options="presetOptions"
          :loading="presetsQuery.isPending.value"
          :disabled="disabled || !appId"
          clearable
          placeholder="使用手动参数"
          @update:model-value="change"
        />
        <AppButton :disabled="disabled || !appId" @click="openPresetManagement">
          管理预设
        </AppButton>
      </div>
      <p v-if="selectedPreset" class="preset-selector__note">
        已选择“{{ selectedPreset.name }}”：{{ shopIds.length }} 家店铺，{{
          overrideShopCount
        }}
        家有单独设置。
      </p>
      <p v-else class="preset-selector__note">
        当前使用手动参数；创建任务后会由服务端固化该次参数。
      </p>
      <div
        v-if="selectedPreset && !preview.length"
        class="preset-selector__preview"
      >
        当前未选择店铺，将仅下发公共参数。
      </div>
      <AppButton
        v-if="selectedPreset && preview.length"
        tone="text"
        class="preset-selector__preview-toggle"
        @click="previewOpen = !previewOpen"
      >
        {{ previewOpen ? '收起本次参数' : '查看本次参数' }}
      </AppButton>
      <div v-if="previewOpen" class="preset-selector__preview-list">
        <div
          v-for="item in preview"
          :key="item.shopId"
          class="preset-selector__preview"
        >
          <div class="preset-selector__preview-heading">
            <strong>{{ item.shopName }}</strong>
            <span>{{ describeShop(item) }}</span>
          </div>
          <dl class="preset-selector__parameters">
            <div v-for="[name, value] in parameterEntries(item)" :key="name">
              <dt>{{ parameterLabel(name) }}</dt>
              <dd>{{ parameterValue(value) }}</dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  </NFormItem>
</template>

<style scoped>
.preset-selector-content {
  width: 100%;
  min-width: 0;
}

.preset-selector {
  display: flex;
  width: 100%;
  min-width: 0;
  align-items: center;
  gap: var(--space-2);
}

.preset-selector > :first-child {
  min-width: 0;
  flex: 1;
}

.preset-selector__note,
.preset-selector__preview {
  margin: var(--space-2) 0 0;
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.preset-selector__preview-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.preset-selector__preview {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-2);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
}

.preset-selector__preview-heading {
  display: flex;
  min-width: 0;
  justify-content: space-between;
  gap: var(--space-2);
}

.preset-selector__preview-heading span {
  color: var(--text-secondary);
}

.preset-selector__parameters {
  display: flex;
  flex-wrap: wrap;
  margin: 0;
  gap: var(--space-2) var(--space-4);
}

.preset-selector__parameters div {
  display: flex;
  gap: var(--space-1);
}

.preset-selector__parameters dt {
  color: var(--text-secondary);
}

.preset-selector__parameters dd {
  margin: 0;
}

.preset-selector__preview-toggle {
  margin-top: var(--space-2);
}
</style>
