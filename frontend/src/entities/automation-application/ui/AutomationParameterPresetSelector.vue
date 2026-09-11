<script setup lang="ts">
import { NFormItem } from 'naive-ui'
import { computed, ref } from 'vue'

import { AppButton, AppSelect } from '@/shared/ui'
import type { ShopSelectOption } from '@/entities/shop'

import type { AutomationInputSchemaDto } from '../api/contracts'
import { useAutomationParameterPresetsQuery } from '../api/queries'
import AutomationParameterPresetManagerDialog from './AutomationParameterPresetManagerDialog.vue'

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

const managerOpen = ref(false)
const presetsQuery = useAutomationParameterPresetsQuery(() => props.appId)
const presets = computed(() => presetsQuery.data.value ?? [])
const selectedPreset = computed(() =>
  presets.value.find((preset) => preset.preset_id === props.modelValue) ?? null,
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
    shopName: props.shopOptions.find((option) => option.value === shopId)?.label ?? shopId,
    parameters: {
      ...preset.common_parameters,
      ...(preset.shop_overrides[shopId] ?? {}),
    },
  }))
})

function change(value: unknown): void {
  emit('update:modelValue', typeof value === 'string' ? value : null)
}
</script>

<template>
  <NFormItem label="参数预设">
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
      <AppButton :disabled="disabled || !appId" @click="managerOpen = true">
        管理预设
      </AppButton>
    </div>
    <p v-if="selectedPreset" class="preset-selector__note">
      已选择“{{ selectedPreset.name }}”；创建任务时由服务端合并并固化当前选中店铺的最终参数。
    </p>
    <div v-if="selectedPreset && !preview.length" class="preset-selector__preview">
      当前未选择店铺，将仅下发公共参数。
    </div>
    <div v-for="item in preview" :key="item.shopId" class="preset-selector__preview">
      <strong>{{ item.shopName }}</strong>
      <span v-for="(value, name) in item.parameters" :key="name">
        {{ name }}={{ String(value) }}
      </span>
    </div>
  </NFormItem>

  <AutomationParameterPresetManagerDialog
    v-model:show="managerOpen"
    :app-id="appId"
    :schema="schema"
    @saved="$emit('update:modelValue', $event.preset_id)"
  />
</template>

<style scoped>
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

.preset-selector__preview {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: var(--space-2);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
}
</style>
