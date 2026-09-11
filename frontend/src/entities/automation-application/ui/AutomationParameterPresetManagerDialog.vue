<script setup lang="ts">
import { NForm, NFormItem, useMessage } from 'naive-ui'
import { computed, reactive, ref, watch } from 'vue'

import { ShopMultiSelector, useShopSelectionOptionsQuery } from '@/entities/shop'
import { getErrorMessage } from '@/shared/api'
import FormDialog from '@/shared/components/FormDialog.vue'
import { AppButton, AppInput, AppSelect } from '@/shared/ui'

import type {
  AutomationInputSchemaDto,
  AutomationParameterPresetDto,
} from '../api/contracts'
import {
  useAutomationParameterPresetsQuery,
  useCopyAutomationParameterPresetMutation,
  useSaveAutomationParameterPresetMutation,
} from '../api/queries'
import {
  createDefaultAutomationParameters,
  mapAutomationParameterFields,
  validateAutomationParameters,
} from '../model/parameters'
import AutomationParameterFields from './AutomationParameterFields.vue'

const props = defineProps<{
  show: boolean
  appId: string | null
  schema: AutomationInputSchemaDto
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  saved: [preset: AutomationParameterPresetDto]
}>()

const message = useMessage()
const presetsQuery = useAutomationParameterPresetsQuery(() => props.appId)
const shopOptionsQuery = useShopSelectionOptionsQuery()
const savePreset = useSaveAutomationParameterPresetMutation()
const copyPreset = useCopyAutomationParameterPresetMutation()
const selectedPresetId = ref<string | null>(null)
const overrideShopIds = ref<string[]>([])
const copyName = ref('')
const draft = reactive({
  name: '',
  commonParameters: {} as Record<string, unknown>,
  shopOverrides: {} as Record<string, Record<string, unknown>>,
  expectedVersion: null as number | null,
})

const presets = computed(() => presetsQuery.data.value ?? [])
const presetOptions = computed(() =>
  presets.value.map((preset) => ({
    label: preset.name,
    value: preset.preset_id,
  })),
)
const shopOptions = computed(() => shopOptionsQuery.data.value ?? [])
const fields = computed(() => mapAutomationParameterFields(props.schema))
const commonError = computed(() =>
  validateAutomationParameters(props.schema, draft.commonParameters),
)
const saveDisabledReason = computed(() => {
  if (!props.appId) return '请先选择影刀应用'
  if (!draft.name.trim()) return '请输入预设名称'
  if (selectedPresetId.value && draft.expectedVersion === null) {
    return '预设版本加载中，请稍后再保存'
  }
  return commonError.value
})

watch(
  [() => props.show, () => props.appId, () => presetsQuery.data.value],
  ([show]) => {
    if (!show) return
    if (selectedPresetId.value) return
    startCreate()
  },
  { immediate: true },
)

function cloneOverrides(
  value: Record<string, Record<string, unknown>>,
): Record<string, Record<string, unknown>> {
  return Object.fromEntries(
    Object.entries(value).map(([shopId, parameters]) => [
      shopId,
      { ...parameters },
    ]),
  )
}

function startCreate(): void {
  selectedPresetId.value = null
  draft.name = ''
  draft.commonParameters = createDefaultAutomationParameters(props.schema)
  draft.shopOverrides = {}
  draft.expectedVersion = null
  overrideShopIds.value = []
  copyName.value = ''
}

function selectPreset(value: unknown): void {
  const presetId = typeof value === 'string' ? value : null
  const preset = presets.value.find((item) => item.preset_id === presetId)
  if (!preset) {
    startCreate()
    return
  }
  selectedPresetId.value = preset.preset_id
  draft.name = preset.name
  draft.commonParameters = { ...preset.common_parameters }
  draft.shopOverrides = cloneOverrides(preset.shop_overrides)
  draft.expectedVersion = preset.version
  overrideShopIds.value = Object.keys(preset.shop_overrides)
  copyName.value = `${preset.name} 副本`
}

function updateOverrideShops(shopIds: string[]): void {
  const allowed = new Set(shopIds)
  draft.shopOverrides = Object.fromEntries(
    Object.entries(draft.shopOverrides).filter(([shopId]) => allowed.has(shopId)),
  )
  for (const shopId of shopIds) {
    if (!draft.shopOverrides[shopId]) draft.shopOverrides[shopId] = {}
  }
  overrideShopIds.value = [...shopIds]
}

function effectiveShopParameters(shopId: string): Record<string, unknown> {
  return {
    ...draft.commonParameters,
    ...(draft.shopOverrides[shopId] ?? {}),
  }
}

function updateShopParameters(
  shopId: string,
  next: Record<string, unknown>,
): void {
  const current = effectiveShopParameters(shopId)
  const overrides = { ...(draft.shopOverrides[shopId] ?? {}) }
  for (const field of fields.value) {
    const name = field.name
    if (next[name] === current[name]) continue
    if (next[name] === draft.commonParameters[name]) delete overrides[name]
    else if (Object.prototype.hasOwnProperty.call(next, name)) overrides[name] = next[name]
    else delete overrides[name]
  }
  draft.shopOverrides[shopId] = overrides
}

function resetShopField(shopId: string, name: string): void {
  const overrides = { ...(draft.shopOverrides[shopId] ?? {}) }
  delete overrides[name]
  draft.shopOverrides[shopId] = overrides
}

function labelForField(name: string): string {
  return fields.value.find((field) => field.name === name)?.label ?? name
}

async function save(): Promise<void> {
  if (!props.appId || saveDisabledReason.value) return
  try {
    const preset = await savePreset.mutateAsync({
      appId: props.appId,
      presetId: selectedPresetId.value,
      data: selectedPresetId.value
        ? {
            name: draft.name.trim(),
            common_parameters: { ...draft.commonParameters },
            shop_overrides: cloneOverrides(draft.shopOverrides),
            expected_version: draft.expectedVersion!,
          }
        : {
        name: draft.name.trim(),
        common_parameters: { ...draft.commonParameters },
        shop_overrides: cloneOverrides(draft.shopOverrides),
          },
    })
    selectPreset(preset.preset_id)
    message.success('参数预设已保存')
    emit('saved', preset)
  } catch (error) {
    message.error(getErrorMessage(error))
  }
}

async function copy(): Promise<void> {
  if (!props.appId || !selectedPresetId.value || !copyName.value.trim()) return
  try {
    const preset = await copyPreset.mutateAsync({
      appId: props.appId,
      presetId: selectedPresetId.value,
      name: copyName.value.trim(),
    })
    selectPreset(preset.preset_id)
    message.success('参数预设已复制')
    emit('saved', preset)
  } catch (error) {
    message.error(getErrorMessage(error))
  }
}
</script>

<template>
  <FormDialog
    :show="show"
    title="管理参数预设"
    size="lg"
    :submitting="savePreset.isPending.value || copyPreset.isPending.value"
    :submit-disabled="Boolean(saveDisabledReason)"
    :submit-disabled-reason="saveDisabledReason"
    @update:show="$emit('update:show', $event)"
    @submit="save"
  >
    <NForm label-placement="top" class="preset-manager">
      <NFormItem label="已保存预设">
        <div class="preset-manager__saved">
          <AppSelect
            :model-value="selectedPresetId"
            :options="presetOptions"
            :loading="presetsQuery.isPending.value"
            clearable
            placeholder="选择预设，或新建"
            @update:model-value="selectPreset"
          />
          <AppButton @click="startCreate">新建</AppButton>
        </div>
      </NFormItem>
      <NFormItem label="预设名称" required>
        <AppInput v-model="draft.name" :maxlength="100" />
      </NFormItem>
      <NFormItem v-if="selectedPresetId" label="复制预设">
        <div class="preset-manager__saved">
          <AppInput v-model="copyName" :maxlength="100" placeholder="复制后的名称" />
          <AppButton :disabled="!copyName.trim()" @click="copy">复制</AppButton>
        </div>
      </NFormItem>

      <section class="preset-manager__section">
        <h3>公共参数</h3>
        <AutomationParameterFields
          v-model="draft.commonParameters"
          :schema="schema"
          preserve-empty-string
        />
      </section>

      <section class="preset-manager__section">
        <h3>店铺参数覆盖</h3>
        <p>只保存与公共参数不同的字段；恢复继承后会继续使用公共参数。</p>
        <ShopMultiSelector
          :model-value="overrideShopIds"
          :options="shopOptions"
          :loading="shopOptionsQuery.isPending.value"
          @update:model-value="updateOverrideShops"
        />
        <section
          v-for="shopId in overrideShopIds"
          :key="shopId"
          class="preset-manager__shop"
        >
          <h4>
            {{ shopOptions.find((option) => option.value === shopId)?.label ?? shopId }}
          </h4>
          <AutomationParameterFields
            :model-value="effectiveShopParameters(shopId)"
            :schema="schema"
            preserve-empty-string
            @update:model-value="updateShopParameters(shopId, $event)"
          />
          <div
            v-if="Object.keys(draft.shopOverrides[shopId] ?? {}).length"
            class="preset-manager__overrides"
          >
            <AppButton
              v-for="name in Object.keys(draft.shopOverrides[shopId] ?? {})"
              :key="name"
              tone="text"
              @click="resetShopField(shopId, name)"
            >
              恢复继承 · {{ labelForField(name) }}
            </AppButton>
          </div>
        </section>
      </section>
    </NForm>
  </FormDialog>
</template>

<style scoped>
.preset-manager,
.preset-manager__section {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-3);
}

.preset-manager__section {
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}

.preset-manager__section h3,
.preset-manager__shop h4,
.preset-manager__section p {
  margin: 0;
}

.preset-manager__section p {
  color: var(--text-secondary);
}

.preset-manager__saved,
.preset-manager__overrides {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--space-2);
}

.preset-manager__saved > :first-child {
  min-width: 0;
  flex: 1;
}

.preset-manager__overrides {
  flex-wrap: wrap;
}

.preset-manager__shop {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
}
</style>
