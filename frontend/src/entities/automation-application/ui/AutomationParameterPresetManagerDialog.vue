<script setup lang="ts">
import {
  NForm,
  NFormItem,
  NTabPane,
  NTabs,
  useMessage,
  type SelectOption,
} from 'naive-ui'
import { computed, reactive, ref, watch } from 'vue'

import {
  ShopMultiSelector,
  useShopSelectionOptionsQuery,
} from '@/entities/shop'
import { toApiError } from '@/shared/api'
import FormDialog from '@/shared/components/FormDialog.vue'
import { AppButton, AppInput, AppSelect } from '@/shared/ui'

import type {
  AutomationInputSchemaDto,
  AutomationParameterPresetDto,
  YingdaoApplicationOptionDto,
} from '../api/contracts'
import {
  useAutomationParameterPresetsQuery,
  useSaveAutomationParameterPresetMutation,
} from '../api/queries'
import {
  createDefaultAutomationParameters,
  mapAutomationParameterFields,
  validateAutomationParameters,
} from '../model/parameters'
import AutomationParameterFields from './AutomationParameterFields.vue'

const props = withDefaults(
  defineProps<{
    show: boolean
    appId: string | null
    schema: AutomationInputSchemaDto
    applicationOptions?: YingdaoApplicationOptionDto[]
    applicationOptionsLoading?: boolean
    initialPresetId?: string | null
    schemaLoading?: boolean
    schemaError?: string | null
    allowSchemaConfiguration?: boolean
  }>(),
  {
    applicationOptions: () => [],
    applicationOptionsLoading: false,
    initialPresetId: null,
    schemaLoading: false,
    schemaError: null,
    allowSchemaConfiguration: false,
  },
)

const emit = defineEmits<{
  'update:show': [value: boolean]
  'update:appId': [value: string | null]
  saved: [preset: AutomationParameterPresetDto]
  configureSchema: [application: YingdaoApplicationOptionDto]
}>()

const message = useMessage()
const presetsQuery = useAutomationParameterPresetsQuery(() => props.appId)
const shopOptionsQuery = useShopSelectionOptionsQuery()
const savePreset = useSaveAutomationParameterPresetMutation()
const selectedPresetId = ref<string | null>(null)
const overrideShopIds = ref<string[]>([])
const selectedOverrideShopId = ref<string | null>(null)
const activeTab = ref<'common' | 'shops'>('common')
const parameterQuery = ref('')
const saveError = ref<string | null>(null)
const nameError = ref<string | null>(null)
const draft = reactive({
  name: '',
  commonParameters: {} as Record<string, unknown>,
  shopOverrides: {} as Record<string, Record<string, unknown>>,
  expectedVersion: null as number | null,
})

const presets = computed(() => presetsQuery.data.value ?? [])
const applicationOptions = computed<SelectOption[]>(() =>
  props.applicationOptions.map((application) => ({
    label: application.app_name,
    value: application.app_id,
  })),
)
const selectedApplication = computed(
  () =>
    props.applicationOptions.find(
      (application) => application.app_id === props.appId,
    ) ?? (props.appId ? { app_id: props.appId, app_name: props.appId } : null),
)
const shopOptions = computed(() => shopOptionsQuery.data.value ?? [])
const fields = computed(() => mapAutomationParameterFields(props.schema))
const filteredSchema = computed(() => {
  const query = parameterQuery.value.trim().toLocaleLowerCase()
  if (!query) return props.schema
  return {
    fields: props.schema.fields.filter((field) =>
      `${field.label} ${field.name}`.toLocaleLowerCase().includes(query),
    ),
  }
})
const commonError = computed(() =>
  validateAutomationParameters(props.schema, draft.commonParameters),
)
const saveDisabledReason = computed(() => {
  if (!props.appId) return '请先选择影刀应用'
  if (props.schemaLoading) return '正在读取应用参数定义'
  if (props.schemaError) return '应用参数定义读取失败，暂时无法保存'
  if (!draft.name.trim()) return '请输入预设名称'
  if (selectedPresetId.value && draft.expectedVersion === null) {
    return '预设版本加载中，请稍后再保存'
  }
  return commonError.value
})

watch(
  () => props.show,
  (show) => {
    if (!show) {
      saveError.value = null
      nameError.value = null
      return
    }
    startCreate()
  },
  { immediate: true },
)

watch(
  () => props.appId,
  (appId, previousAppId) => {
    if (!props.show || appId === previousAppId) return
    startCreate()
  },
)

watch(
  [
    () => props.initialPresetId,
    () => presetsQuery.data.value,
    () => props.show,
  ],
  ([presetId, available, show]) => {
    if (!show || !presetId || !available?.length) return
    const preset = available.find((item) => item.preset_id === presetId)
    if (preset && selectedPresetId.value !== preset.preset_id) {
      selectPreset(preset.preset_id)
    }
  },
  { immediate: true },
)

watch(
  [fields, () => props.show, () => selectedPresetId.value],
  ([nextFields, show, presetId]) => {
    if (!show || presetId || !nextFields.length) return
    // A schema can be created while this dialog remains open.  Fill only
    // absent values so the user returns to the same draft instead of losing
    // an explicit `0`, `false`, or empty string.
    draft.commonParameters = {
      ...createDefaultAutomationParameters(
        props.schema,
        draft.commonParameters,
      ),
      ...draft.commonParameters,
    }
  },
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
  selectedOverrideShopId.value = null
  activeTab.value = 'common'
  parameterQuery.value = ''
  saveError.value = null
  nameError.value = null
}

function selectPreset(value: unknown): void {
  const presetId = typeof value === 'string' ? value : null
  const preset = presets.value.find((item) => item.preset_id === presetId)
  if (!preset) {
    startCreate()
    return
  }
  applyPreset(preset)
}

function applyPreset(
  preset: AutomationParameterPresetDto,
  { preserveEditorView = false }: { preserveEditorView?: boolean } = {},
): void {
  const previousOverrideShopId = selectedOverrideShopId.value
  selectedPresetId.value = preset.preset_id
  draft.name = preset.name
  draft.commonParameters = { ...preset.common_parameters }
  draft.shopOverrides = cloneOverrides(preset.shop_overrides)
  draft.expectedVersion = preset.version
  overrideShopIds.value = Object.keys(preset.shop_overrides)
  selectedOverrideShopId.value =
    preserveEditorView &&
    previousOverrideShopId &&
    overrideShopIds.value.includes(previousOverrideShopId)
      ? previousOverrideShopId
      : (overrideShopIds.value[0] ?? null)
  if (!preserveEditorView) {
    activeTab.value = 'common'
    parameterQuery.value = ''
  }
  saveError.value = null
  nameError.value = null
}

function changeApplication(value: unknown): void {
  const appId = typeof value === 'string' ? value : null
  if (appId === props.appId) return
  emit('update:appId', appId)
}

function updateOverrideShops(shopIds: string[]): void {
  const allowed = new Set(shopIds)
  draft.shopOverrides = Object.fromEntries(
    Object.entries(draft.shopOverrides).filter(([shopId]) =>
      allowed.has(shopId),
    ),
  )
  for (const shopId of shopIds) {
    if (!draft.shopOverrides[shopId]) draft.shopOverrides[shopId] = {}
  }
  overrideShopIds.value = [...shopIds]
  if (
    !selectedOverrideShopId.value ||
    !allowed.has(selectedOverrideShopId.value)
  ) {
    selectedOverrideShopId.value = shopIds[0] ?? null
  }
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
    else if (Object.prototype.hasOwnProperty.call(next, name))
      overrides[name] = next[name]
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

function shopName(shopId: string): string {
  return (
    shopOptions.value.find((option) => option.value === shopId)?.label ?? shopId
  )
}

function overrideSummary(shopId: string): string {
  const names = Object.keys(draft.shopOverrides[shopId] ?? {})
  if (!names.length) return '使用公共参数'
  return `已单独设置：${names.map(labelForField).join('、')}`
}

function selectOverrideShop(shopId: string): void {
  selectedOverrideShopId.value = shopId
}

function clearNameError(): void {
  nameError.value = null
  saveError.value = null
}

function applySaveError(error: unknown): void {
  const apiError = toApiError(error)
  if (apiError.code === 'AUTOMATION_PARAMETER_PRESET_CONFLICT') {
    nameError.value = apiError.message
    return
  }
  const unknownParameters = apiError.message.match(/^未知参数:\s*(.+)$/)?.[1]
  if (unknownParameters) {
    const names = unknownParameters.split(',').map((name) => name.trim())
    if (
      names.some((name) =>
        Object.prototype.hasOwnProperty.call(draft.commonParameters, name),
      )
    ) {
      activeTab.value = 'common'
      saveError.value = `公共参数包含服务端已不再定义的字段：${names.join('、')}`
      return
    }
    const matchedShopId = overrideShopIds.value.find((shopId) =>
      names.some((name) =>
        Object.prototype.hasOwnProperty.call(
          draft.shopOverrides[shopId] ?? {},
          name,
        ),
      ),
    )
    if (matchedShopId) {
      activeTab.value = 'shops'
      selectedOverrideShopId.value = matchedShopId
      saveError.value = `店铺“${shopName(matchedShopId)}”包含服务端已不再定义的字段：${names.join('、')}`
      return
    }
  }
  saveError.value =
    apiError.code === 'AUTOMATION_PARAMETER_PRESET_VERSION_CONFLICT'
      ? `${apiError.message}。请重新读取后决定是否覆盖。`
      : apiError.message
}

async function save(): Promise<void> {
  if (!props.appId || saveDisabledReason.value) return
  saveError.value = null
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
    applyPreset(preset, { preserveEditorView: true })
    message.success('参数预设已保存')
    emit('saved', preset)
  } catch (error) {
    applySaveError(error)
  }
}

function openSchemaConfiguration(): void {
  if (selectedApplication.value)
    emit('configureSchema', selectedApplication.value)
}
</script>

<template>
  <FormDialog
    :show="show"
    :title="selectedPresetId ? '编辑配置' : '新建配置'"
    size="lg"
    :submitting="savePreset.isPending.value"
    :submit-disabled="Boolean(saveDisabledReason)"
    :submit-disabled-reason="saveDisabledReason"
    @update:show="$emit('update:show', $event)"
    @submit="save"
  >
    <NForm label-placement="top" class="preset-manager">
      <NFormItem
        v-if="applicationOptions.length && !selectedPresetId"
        label="对应应用"
        required
      >
        <AppSelect
          :model-value="appId"
          :options="applicationOptions"
          :loading="applicationOptionsLoading"
          placeholder="选择影刀应用"
          @update:model-value="changeApplication"
        />
      </NFormItem>
      <NFormItem v-else-if="selectedApplication" label="对应应用">
        <AppInput :model-value="selectedApplication.app_name" disabled />
      </NFormItem>
      <NFormItem
        label="预设名称"
        required
        :validation-status="nameError ? 'error' : undefined"
        :feedback="nameError ?? undefined"
      >
        <AppInput
          v-model="draft.name"
          :maxlength="100"
          name="automation-parameter-preset-name"
          autocomplete="off"
          aria-label="预设名称"
          @update:model-value="clearNameError"
        />
      </NFormItem>

      <p v-if="saveError" class="preset-manager__error" role="alert">
        保存失败：{{ saveError }}。草稿仍已保留，请修正后重试。
      </p>
      <p v-if="schemaError" class="preset-manager__error" role="alert">
        参数定义读取失败：{{ schemaError }}
      </p>

      <section class="preset-manager__schema-summary">
        <div>
          <p v-if="schemaLoading">正在读取参数定义。</p>
          <p v-else-if="!fields.length">
            该应用尚未配置参数字段。字段定义由应用共用，预设值彼此独立。
          </p>
          <p v-else>当前应用已有 {{ fields.length }} 个共用参数字段。</p>
        </div>
        <AppButton
          v-if="allowSchemaConfiguration"
          :disabled="!selectedApplication"
          @click="openSchemaConfiguration"
        >
          管理字段
        </AppButton>
      </section>

      <NTabs
        v-model:value="activeTab"
        type="line"
        animated
        class="preset-manager__tabs"
      >
        <NTabPane name="common" tab="公共参数">
          <div class="preset-manager__tab-content">
            <AppInput
              v-if="fields.length"
              v-model="parameterQuery"
              clearable
              placeholder="搜索参数"
            />
            <AutomationParameterFields
              v-if="fields.length"
              v-model="draft.commonParameters"
              :schema="filteredSchema"
              :disabled="schemaLoading"
              preserve-empty-string
            />
            <p v-else class="preset-manager__hint">
              请先配置字段；返回后会保留当前预设名称和未保存草稿。
            </p>
          </div>
        </NTabPane>
        <NTabPane
          name="shops"
          :tab="`店铺差异 ${overrideShopIds.length ? `(${overrideShopIds.length})` : ''}`"
        >
          <div class="preset-manager__tab-content">
            <p class="preset-manager__hint">
              仅保存与公共参数不同的字段；恢复继承后继续使用公共参数。
            </p>
            <ShopMultiSelector
              :model-value="overrideShopIds"
              :options="shopOptions"
              :loading="shopOptionsQuery.isPending.value"
              :disabled="schemaLoading || !appId"
              @update:model-value="updateOverrideShops"
            />
            <div
              v-if="overrideShopIds.length"
              class="preset-manager__shop-list"
            >
              <AppButton
                v-for="shopId in overrideShopIds"
                :key="shopId"
                :tone="selectedOverrideShopId === shopId ? 'primary' : 'text'"
                class="preset-manager__shop-summary"
                @click="selectOverrideShop(shopId)"
              >
                <strong>{{ shopName(shopId) }}</strong>
                <span>{{ overrideSummary(shopId) }}</span>
              </AppButton>
            </div>
            <section
              v-if="selectedOverrideShopId"
              class="preset-manager__shop-editor"
            >
              <div class="preset-manager__section-heading">
                <div>
                  <h3>{{ shopName(selectedOverrideShopId) }}</h3>
                  <p class="preset-manager__hint">
                    {{ overrideSummary(selectedOverrideShopId) }}
                  </p>
                </div>
              </div>
              <AppInput
                v-if="fields.length"
                v-model="parameterQuery"
                clearable
                placeholder="搜索参数"
              />
              <AutomationParameterFields
                v-if="fields.length"
                :model-value="effectiveShopParameters(selectedOverrideShopId)"
                :schema="filteredSchema"
                :disabled="schemaLoading"
                preserve-empty-string
                @update:model-value="
                  updateShopParameters(selectedOverrideShopId, $event)
                "
              />
              <div
                v-if="
                  Object.keys(draft.shopOverrides[selectedOverrideShopId] ?? {})
                    .length
                "
                class="preset-manager__overrides"
              >
                <AppButton
                  v-for="name in Object.keys(
                    draft.shopOverrides[selectedOverrideShopId] ?? {},
                  )"
                  :key="name"
                  tone="text"
                  @click="resetShopField(selectedOverrideShopId, name)"
                >
                  恢复继承 · {{ labelForField(name) }}
                </AppButton>
              </div>
            </section>
          </div>
        </NTabPane>
      </NTabs>
    </NForm>
  </FormDialog>
</template>

<style scoped>
.preset-manager,
.preset-manager__tab-content,
.preset-manager__shop-editor {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-3);
}

.preset-manager__schema-summary p,
.preset-manager__section-heading h3,
.preset-manager__section-heading p {
  margin: 0;
}

.preset-manager__section p,
.preset-manager__hint {
  color: var(--text-secondary);
}

.preset-manager__schema-summary,
.preset-manager__section-heading,
.preset-manager__overrides {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--space-2);
}

.preset-manager__schema-summary {
  justify-content: space-between;
}

.preset-manager__section-heading {
  align-items: flex-start;
}

.preset-manager__overrides {
  flex-wrap: wrap;
}

.preset-manager__tabs {
  min-width: 0;
}

.preset-manager__tab-content {
  padding-top: var(--space-2);
}

.preset-manager__shop-list {
  display: grid;
  gap: var(--space-2);
}

.preset-manager__shop-summary {
  display: flex;
  width: 100%;
  justify-content: flex-start;
  gap: var(--space-2);
  overflow: hidden;
  text-align: left;
}

.preset-manager__shop-summary span {
  overflow: hidden;
  color: var(--text-secondary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preset-manager__shop-editor {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
}

.preset-manager__error {
  margin: 0;
  color: var(--color-error);
}
</style>
