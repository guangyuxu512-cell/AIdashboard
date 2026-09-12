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
const pendingCommonParameterNames = ref<string[]>([])
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
const selectedCommonParameterNames = computed(() =>
  new Set(Object.keys(draft.commonParameters)),
)
const displayedCommonSchema = computed(() => ({
  fields: props.schema.fields.filter(
    (field) =>
      field.required ||
      selectedCommonParameterNames.value.has(field.name) ||
      pendingCommonParameterNames.value.includes(field.name),
  ),
}))
const filteredCommonSchema = computed(() => {
  const query = commonParameterQuery.value.trim().toLocaleLowerCase()
  if (!query) return displayedCommonSchema.value
  return {
    fields: displayedCommonSchema.value.fields.filter((field) =>
      `${field.label} ${field.name}`.toLocaleLowerCase().includes(query),
    ),
  }
})
const addableCommonParameterOptions = computed<SelectOption[]>(() =>
  props.schema.fields
    .filter(
      (field) =>
        !selectedCommonParameterNames.value.has(field.name) &&
        !pendingCommonParameterNames.value.includes(field.name),
    )
    .map((field) => ({ label: field.label || field.name, value: field.name })),
)
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
  if (pendingCommonParameterNames.value.length) {
    return '请填写新添加的参数后再保存'
  }
  return commonError.value
})
const editingShopName = computed(() =>
  editingShopId.value ? shopName(editingShopId.value) : '',
)
const editingShopOverrides = computed(() =>
  editingShopId.value ? (draft.shopOverrides[editingShopId.value] ?? {}) : {},
)
const editingShopSchema = computed(() => {
  const selectedNames = new Set([
    ...Object.keys(draft.commonParameters),
    ...Object.keys(editingShopOverrides.value),
  ])
  return {
    fields: props.schema.fields.filter((field) => selectedNames.has(field.name)),
  }
})

watch(
  () => props.show,
  (show) => {
    if (!show) {
      saveError.value = null
      nameError.value = null
      shopOverrideDialogVisible.value = false
      editingShopId.value = null
      pendingNewShopId.value = null
      pendingCommonParameterNames.value = []
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
  // Application fields are a shared catalog.  A new preset starts with no
  // optional fields selected; adding a field is an explicit preset fact.
  draft.commonParameters = {}
  draft.shopOverrides = {}
  draft.expectedVersion = null
  commonParameterQuery.value = ''
  pendingCommonParameterNames.value = []
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
  pendingCommonParameterNames.value = []
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
  if (fields.value.some((field) => field.name === name && field.required)) return
  const next = { ...draft.commonParameters }
  delete next[name]
  draft.commonParameters = next
  pendingCommonParameterNames.value = pendingCommonParameterNames.value.filter(
    (item) => item !== name,
  )
}

function addCommonParameter(value: unknown): void {
  const name = typeof value === 'string' ? value : null
  const field = props.schema.fields.find((item) => item.name === name)
  if (!field || selectedCommonParameterNames.value.has(field.name)) return
  if (field.default_value !== null) {
    draft.commonParameters = {
      ...draft.commonParameters,
      [field.name]: field.default_value,
    }
    return
  }
  pendingCommonParameterNames.value = [
    ...pendingCommonParameterNames.value,
    field.name,
  ]
}

function updateCommonParameters(values: Record<string, unknown>): void {
  draft.commonParameters = values
  pendingCommonParameterNames.value = pendingCommonParameterNames.value.filter(
    (name) => !Object.hasOwn(values, name),
  )
}

function shopName(shopId: string): string {
  return (
    shopOptions.value.find((option) => option.value === shopId)?.label ?? shopId
  )
}

function overrideSummary(shopId: string): string {
  const values = draft.shopOverrides[shopId] ?? {}
  const entries = Object.entries(values)
  if (!entries.length) return '使用公共参数'
  const summary = entries
    .slice(0, 2)
    .map(([name, value]) => `${labelForField(name)}：${valueText(value)}`)
  if (entries.length > summary.length) summary.push(`等 ${entries.length} 项`)
  return summary.join('；')
}

function fullOverrideSummary(shopId: string): string {
  return Object.entries(draft.shopOverrides[shopId] ?? {})
    .map(([name, value]) => `${labelForField(name)}：${valueText(value)}`)
    .join('；')
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
    submit-text="保存配置"
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
            <p v-else class="preset-manager__hint">
              {{ displayedCommonSchema.fields.length }} 项当前参数
            </p>
          </div>
          <div class="preset-manager__section-actions">
            <AppSelect
              v-if="addableCommonParameterOptions.length"
              :model-value="null"
              :options="addableCommonParameterOptions"
              :disabled="schemaLoading"
              placeholder="+ 添加参数"
              class="preset-manager__add-parameter"
              @update:model-value="addCommonParameter"
            />
            <AppButton
              v-if="allowSchemaConfiguration"
              :disabled="!selectedApplication"
              @click="openSchemaConfiguration"
            >
              管理字段
            </AppButton>
          </div>
        </div>
        <AppInput
          v-if="fields.length"
          v-model="commonParameterQuery"
          clearable
          placeholder="搜索参数"
        />
        <div v-if="fields.length" class="preset-manager__parameter-viewport">
          <div class="preset-manager__parameter-headings" aria-hidden="true">
            <span>字段名</span>
            <span>值</span>
            <span>移除</span>
          </div>
          <AutomationParameterFields
            v-model="draft.commonParameters"
            :schema="filteredCommonSchema"
            :disabled="schemaLoading"
            layout="compact"
            preserve-empty-string
            show-remove
            @update:model-value="updateCommonParameters"
            @remove="removeCommonParameter"
          />
        </div>
        <section v-if="unknownCommonParameterNames.length" class="preset-manager__legacy">
          <h4>待修正字段</h4>
          <p>这些旧值已不在当前应用字段定义中；移除只影响当前配置，不会删除应用共用字段。</p>
          <div v-for="name in unknownCommonParameterNames" :key="name">
            <span>{{ name }}：{{ valueText(draft.commonParameters[name]) }}</span>
            <AppButton tone="text" @click="removeCommonParameter(name)">移除旧值</AppButton>
          </div>
        </section>
      </section>

      <section class="preset-manager__section">
        <div class="preset-manager__section-heading">
          <div>
            <h3>店铺差异</h3>
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
            <span :title="fullOverrideSummary(shopId)">{{ overrideSummary(shopId) }}</span>
            <div>
              <AppButton tone="text" @click="openShopOverride(shopId)">修改</AppButton>
              <AppButton tone="text" @click="removeOverrideShop(shopId)">移除</AppButton>
            </div>
          </div>
        </div>
        <p v-else class="preset-manager__hint">尚未添加店铺差异</p>
      </section>
    </NForm>
  </FormDialog>

  <AutomationParameterPresetShopOverrideDialog
    :show="shopOverrideDialogVisible"
    :shop-id="editingShopId"
    :shop-name="editingShopName"
    :schema="editingShopSchema"
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

.preset-manager__section-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: var(--space-2);
}

.preset-manager__section-heading h3,
.preset-manager__section-heading p,
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
.preset-manager__shop-row span,
.preset-manager__legacy p {
  color: var(--text-secondary);
}

.preset-manager__error {
  color: var(--color-error);
}

.preset-manager__parameter-viewport {
  /* A compact NForm row includes the control plus its form-item spacing. */
  --schema-parameter-label-column: var(--field-width-xs);
  --schema-parameter-action-column: 48px;
  --preset-parameter-row-height: calc(
    var(--control-height-default) + var(--space-8)
  );
  max-height: calc(var(--preset-parameter-row-height) * 5);
  overflow-y: auto;
  padding-right: var(--space-2);
}

.preset-manager__parameter-headings {
  display: grid;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
  grid-template-columns:
    var(--schema-parameter-label-column) minmax(0, 1fr)
    var(--schema-parameter-action-column);
}

.preset-manager__parameter-headings span:last-child {
  text-align: center;
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

.preset-manager__add-parameter {
  width: min(180px, 40vw);
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

@media (min-height: 1100px) {
  .preset-manager__parameter-viewport {
    max-height: calc(var(--preset-parameter-row-height) * 8);
  }
}

@media (max-height: 700px) {
  .preset-manager__parameter-viewport {
    max-height: calc(var(--preset-parameter-row-height) * 3);
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

  .preset-manager__section-actions {
    width: 100%;
    justify-content: space-between;
  }

  .preset-manager__add-shop {
    width: 100%;
  }

  .preset-manager__parameter-headings {
    display: none;
  }
}
</style>
