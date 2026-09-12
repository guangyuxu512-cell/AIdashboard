<script setup lang="ts">
import { NForm, NFormItem, useMessage, type SelectOption } from 'naive-ui'
import { computed, reactive, ref, watch } from 'vue'

import { useShopSelectionOptionsQuery } from '@/entities/shop'
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
import AutomationParameterPresetShopOverrideDialog from './AutomationParameterPresetShopOverrideDialog.vue'

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
const commonParameterQuery = ref('')
const saveError = ref<string | null>(null)
const nameError = ref<string | null>(null)
const shopOverrideDialogVisible = ref(false)
const editingShopId = ref<string | null>(null)
const pendingNewShopId = ref<string | null>(null)
const draft = reactive({
  name: '',
  commonParameters: {} as Record<string, unknown>,
  shopOverrides: {} as Record<string, Record<string, unknown>>,
  expectedVersion: null as number | null,
})

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
const availableShopOptions = computed<SelectOption[]>(() =>
  shopOptions.value.filter(
    (option) => !Object.hasOwn(draft.shopOverrides, String(option.value)),
  ),
)
const overrideShopIds = computed(() => Object.keys(draft.shopOverrides))
const fields = computed(() => mapAutomationParameterFields(props.schema))
const filteredCommonSchema = computed(() => {
  const query = commonParameterQuery.value.trim().toLocaleLowerCase()
  if (!query) return props.schema
  return {
    fields: props.schema.fields.filter((field) =>
      `${field.label} ${field.name}`.toLocaleLowerCase().includes(query),
    ),
  }
})
const unknownCommonParameterNames = computed(() => {
  const known = new Set(fields.value.map((field) => field.name))
  return Object.keys(draft.commonParameters).filter((name) => !known.has(name))
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
const editingShopName = computed(() =>
  editingShopId.value ? shopName(editingShopId.value) : '',
)
const editingShopOverrides = computed(() =>
  editingShopId.value ? (draft.shopOverrides[editingShopId.value] ?? {}) : {},
)

watch(
  () => props.show,
  (show) => {
    if (!show) {
      saveError.value = null
      nameError.value = null
      shopOverrideDialogVisible.value = false
      editingShopId.value = null
      pendingNewShopId.value = null
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
    if (preset && selectedPresetId.value !== preset.preset_id) applyPreset(preset)
  },
  { immediate: true },
)

watch(
  [fields, () => props.show, () => selectedPresetId.value],
  ([nextFields, show, presetId]) => {
    if (!show || presetId || !nextFields.length) return
    draft.commonParameters = {
      ...createDefaultAutomationParameters(props.schema, draft.commonParameters),
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
  commonParameterQuery.value = ''
  saveError.value = null
  nameError.value = null
  pendingNewShopId.value = null
}

function applyPreset(preset: AutomationParameterPresetDto): void {
  selectedPresetId.value = preset.preset_id
  draft.name = preset.name
  draft.commonParameters = { ...preset.common_parameters }
  draft.shopOverrides = cloneOverrides(preset.shop_overrides)
  draft.expectedVersion = preset.version
  commonParameterQuery.value = ''
  saveError.value = null
  nameError.value = null
}

function changeApplication(value: unknown): void {
  const appId = typeof value === 'string' ? value : null
  if (appId === props.appId) return
  emit('update:appId', appId)
}

function addOverrideShop(value: unknown): void {
  const shopId = typeof value === 'string' ? value : null
  if (!shopId || Object.hasOwn(draft.shopOverrides, shopId)) return
  pendingNewShopId.value = shopId
  openShopOverride(shopId)
}

function openShopOverride(shopId: string): void {
  editingShopId.value = shopId
  shopOverrideDialogVisible.value = true
}

function updateShopOverrides(overrides: Record<string, unknown>): void {
  const shopId = editingShopId.value
  if (!shopId) return
  draft.shopOverrides[shopId] = { ...overrides }
  pendingNewShopId.value = null
}

function updateShopOverrideDialog(show: boolean): void {
  shopOverrideDialogVisible.value = show
  if (!show) {
    if (editingShopId.value === pendingNewShopId.value) {
      pendingNewShopId.value = null
    }
    editingShopId.value = null
  }
}

function removeOverrideShop(shopId: string): void {
  const next = cloneOverrides(draft.shopOverrides)
  delete next[shopId]
  draft.shopOverrides = next
  if (pendingNewShopId.value === shopId) pendingNewShopId.value = null
  if (editingShopId.value === shopId) {
    shopOverrideDialogVisible.value = false
    editingShopId.value = null
  }
}

function removeCommonParameter(name: string): void {
  const next = { ...draft.commonParameters }
  delete next[name]
  draft.commonParameters = next
}

function shopName(shopId: string): string {
  return (
    shopOptions.value.find((option) => option.value === shopId)?.label ?? shopId
  )
}

function overrideSummary(shopId: string): string {
  const values = draft.shopOverrides[shopId] ?? {}
  const names = Object.keys(values)
  if (!names.length) return '使用公共参数'
  return `已单独设置：${names.map(labelForField).join('、')}`
}

function labelForField(name: string): string {
  return fields.value.find((field) => field.name === name)?.label ?? name
}

function valueText(value: unknown): string {
  if (value === '') return '（空）'
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
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
      saveError.value = `店铺“${shopName(matchedShopId)}”包含服务端已不再定义的字段：${names.join('、')}`
      openShopOverride(matchedShopId)
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
    applyPreset(preset)
    message.success('参数预设已保存')
    emit('saved', preset)
  } catch (error) {
    applySaveError(error)
  }
}

function openSchemaConfiguration(): void {
  if (selectedApplication.value) {
    emit('configureSchema', selectedApplication.value)
  }
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
      <div class="preset-manager__identity">
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
      </div>

      <p v-if="saveError" class="preset-manager__error" role="alert">
        保存失败：{{ saveError }}。草稿仍已保留，请修正后重试。
      </p>
      <p v-if="schemaError" class="preset-manager__error" role="alert">
        参数定义读取失败：{{ schemaError }}
      </p>

      <section class="preset-manager__section">
        <div class="preset-manager__section-heading">
          <div>
            <h3>公共参数</h3>
            <p v-if="schemaLoading" class="preset-manager__hint">正在读取参数定义。</p>
            <p v-else-if="!fields.length" class="preset-manager__hint">
              该应用尚未配置参数字段。
            </p>
            <p v-else class="preset-manager__hint">{{ fields.length }} 个应用共用字段</p>
          </div>
          <AppButton
            v-if="allowSchemaConfiguration"
            :disabled="!selectedApplication"
            @click="openSchemaConfiguration"
          >
            管理字段
          </AppButton>
        </div>
        <p class="preset-manager__scope-note">
          字段定义会影响该应用的全部配置；此处仅编辑当前配置的值。
        </p>
        <AppInput
          v-if="fields.length"
          v-model="commonParameterQuery"
          clearable
          placeholder="搜索参数"
        />
        <div v-if="fields.length" class="preset-manager__parameter-viewport">
          <AutomationParameterFields
            v-model="draft.commonParameters"
            :schema="filteredCommonSchema"
            :disabled="schemaLoading"
            preserve-empty-string
          />
        </div>
        <section v-if="unknownCommonParameterNames.length" class="preset-manager__legacy">
          <h4>待修正字段</h4>
          <p>这些旧值已不在当前应用字段定义中；移除只影响当前配置，不会删除应用共用字段。</p>
          <div v-for="name in unknownCommonParameterNames" :key="name">
            <span>{{ name }}：{{ valueText(draft.commonParameters[name]) }}</span>
            <AppButton tone="danger" @click="removeCommonParameter(name)">移除旧值</AppButton>
          </div>
        </section>
      </section>

      <section class="preset-manager__section">
        <div class="preset-manager__section-heading">
          <div>
            <h3>店铺差异</h3>
            <p class="preset-manager__hint">仅保存与公共参数不同的字段。</p>
          </div>
          <AppSelect
            :model-value="null"
            :options="availableShopOptions"
            :loading="shopOptionsQuery.isPending.value"
            :disabled="schemaLoading || !appId"
            placeholder="+ 添加店铺"
            class="preset-manager__add-shop"
            @update:model-value="addOverrideShop"
          />
        </div>
        <div v-if="overrideShopIds.length" class="preset-manager__shop-list">
          <div
            v-for="shopId in overrideShopIds"
            :key="shopId"
            class="preset-manager__shop-row"
          >
            <strong>{{ shopName(shopId) }}</strong>
            <span>{{ overrideSummary(shopId) }}</span>
            <div>
              <AppButton tone="text" @click="openShopOverride(shopId)">修改</AppButton>
              <AppButton tone="danger" @click="removeOverrideShop(shopId)">移除</AppButton>
            </div>
          </div>
        </div>
        <p v-else class="preset-manager__hint">尚未添加店铺差异；所有店铺将使用公共参数。</p>
      </section>
    </NForm>
  </FormDialog>

  <AutomationParameterPresetShopOverrideDialog
    :show="shopOverrideDialogVisible"
    :shop-id="editingShopId"
    :shop-name="editingShopName"
    :schema="schema"
    :common-parameters="draft.commonParameters"
    :shop-overrides="editingShopOverrides"
    :disabled="schemaLoading"
    @update:show="updateShopOverrideDialog"
    @confirm="updateShopOverrides"
  />
</template>

<style scoped>
.preset-manager,
.preset-manager__section,
.preset-manager__legacy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-3);
}

.preset-manager__identity {
  display: grid;
  gap: 0 var(--space-3);
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
}

.preset-manager__section {
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}

.preset-manager__section-heading,
.preset-manager__shop-row,
.preset-manager__legacy > div {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.preset-manager__section-heading h3,
.preset-manager__section-heading p,
.preset-manager__scope-note,
.preset-manager__legacy h4,
.preset-manager__legacy p,
.preset-manager__error {
  margin: 0;
}

.preset-manager__section-heading h3 {
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
}

.preset-manager__hint,
.preset-manager__scope-note,
.preset-manager__shop-row span,
.preset-manager__legacy p {
  color: var(--text-secondary);
}

.preset-manager__error {
  color: var(--color-error);
}

.preset-manager__scope-note {
  font-size: var(--font-size-secondary);
}

.preset-manager__parameter-viewport {
  max-height: 352px;
  overflow-y: auto;
  padding-right: var(--space-2);
}

.preset-manager__legacy {
  padding: var(--space-3);
  border: 1px solid var(--color-warning);
  border-radius: var(--radius-card);
}

.preset-manager__legacy h4 {
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-semibold);
}

.preset-manager__legacy > div span {
  min-width: 0;
  overflow-wrap: anywhere;
}

.preset-manager__add-shop {
  width: min(220px, 45%);
}

.preset-manager__shop-list {
  display: flex;
  max-height: 240px;
  flex-direction: column;
  gap: var(--space-2);
  overflow-y: auto;
}

.preset-manager__shop-row {
  display: grid;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  gap: var(--space-3);
  grid-template-columns: minmax(120px, 0.8fr) minmax(0, 1.6fr) auto;
}

.preset-manager__shop-row strong,
.preset-manager__shop-row span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preset-manager__shop-row > div {
  display: flex;
  gap: var(--space-2);
}

@media (min-height: 900px) {
  .preset-manager__parameter-viewport {
    max-height: 560px;
  }
}

@media (max-height: 700px) {
  .preset-manager__parameter-viewport {
    max-height: 230px;
  }

  .preset-manager__shop-list {
    max-height: 150px;
  }
}

@media (max-width: 720px) {
  .preset-manager__identity,
  .preset-manager__shop-row {
    grid-template-columns: 1fr;
  }

  .preset-manager__section-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .preset-manager__add-shop {
    width: 100%;
  }
}
</style>
