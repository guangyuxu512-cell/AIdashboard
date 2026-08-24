<script setup lang="ts">
import type { SelectOption } from 'naive-ui'
import { NForm, NFormItem } from 'naive-ui'
import { computed, reactive, ref, watch } from 'vue'

import {
  AutomationParameterFields,
  createDefaultAutomationParameters,
  useAutomationApplicationConfigQuery,
  validateAutomationParameters,
} from '@/entities/automation-application'
import { useDeviceProviderInventoriesQuery } from '@/entities/device'
import type {
  ScheduleDetailViewModel,
  ScheduleSaveInput,
} from '@/entities/schedule'
import { getErrorMessage } from '@/shared/api'
import FormDialog from '@/shared/components/FormDialog.vue'
import { AppInput, AppSelect, AppSwitch, AppTimePicker } from '@/shared/ui'
import type { AppOptionValue } from '@/shared/ui/types'

const props = defineProps<{
  show: boolean
  mode: 'create' | 'edit'
  schedule: ScheduleDetailViewModel | null
  deviceOptions: SelectOption[]
  deviceOptionsLoading?: boolean
  submitting?: boolean
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  submit: [input: ScheduleSaveInput]
}>()

const currentTimezone =
  Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai'
const supportedValuesOf = (
  Intl as unknown as {
    supportedValuesOf?: (key: 'timeZone') => string[]
  }
).supportedValuesOf
const timezoneOptions: SelectOption[] = Array.from(
  new Set([
    currentTimezone,
    'Asia/Shanghai',
    ...(supportedValuesOf?.('timeZone') ?? []),
  ]),
).map((value) => ({ label: value, value }))

const form = reactive({
  name: '',
  deviceId: null as string | null,
  applicationId: null as string | null,
  localTimeValue: null as number | null,
  timezone: currentTimezone,
  enabled: true,
  parameters: {} as Record<string, unknown>,
})
const initializedKey = ref('')
const inventoryQuery = useDeviceProviderInventoriesQuery(
  computed(() => form.deviceId),
)
const applicationId = computed(() => form.applicationId)
const configQuery = useAutomationApplicationConfigQuery(applicationId)
const schema = computed(
  () => configQuery.data.value?.input_schema ?? { fields: [] },
)
const applications = computed(
  () => inventoryQuery.data.value?.applications ?? [],
)
const inventoryHasData = computed(() => inventoryQuery.data.value !== undefined)
const inventoryInitialError = computed(
  () => Boolean(inventoryQuery.error.value) && !inventoryHasData.value,
)
const applicationOptions = computed<SelectOption[]>(() => {
  const options = applications.value.map((application) => ({
    label: application.appName,
    value: application.appId,
  }))
  if (
    props.schedule &&
    form.applicationId === props.schedule.applicationId &&
    !options.some((option) => option.value === props.schedule?.applicationId)
  ) {
    options.unshift({
      label: props.schedule.executionName,
      value: props.schedule.applicationId,
    })
  }
  return options
})
const configHasData = computed(() => configQuery.data.value !== undefined)
const configInitialLoading = computed(
  () => configQuery.isPending.value && !configHasData.value,
)
const configInitialError = computed(
  () => Boolean(configQuery.error.value) && !configHasData.value,
)

const disabledReason = computed(() => {
  if (!form.name.trim()) return '请填写计划名称'
  if (!form.deviceId) return '请选择执行设备'
  if (!form.applicationId) return '请选择影刀应用'
  if (form.localTimeValue === null) return '请选择每日执行时间'
  if (!form.timezone) return '请选择时区'
  if (inventoryInitialError.value) return '设备影刀应用读取失败'
  if (configInitialLoading.value) return '正在读取应用参数配置'
  if (configInitialError.value) return '应用参数配置读取失败'
  return validateAutomationParameters(schema.value, form.parameters)
})

watch(
  [() => props.show, () => props.mode, () => props.schedule],
  ([show, mode, schedule]) => {
    if (!show) {
      initializedKey.value = ''
      return
    }
    const key =
      mode === 'edit' ? `edit:${schedule?.scheduleId ?? ''}` : 'create'
    if (key === initializedKey.value || (mode === 'edit' && !schedule)) return
    initializedKey.value = key
    form.name = schedule?.name ?? ''
    form.deviceId = schedule?.deviceId ?? null
    form.applicationId = schedule?.applicationId ?? null
    form.localTimeValue = schedule
      ? localTimeToValue(schedule.localTime)
      : localTimeToValue('09:00')
    form.timezone = schedule?.timezone ?? currentTimezone
    form.enabled = schedule?.enabled ?? true
    form.parameters = { ...(schedule?.parameters ?? {}) }
  },
  { immediate: true },
)

watch(
  [() => props.show, () => form.applicationId, () => configQuery.data.value],
  ([show, appId, config], previous) => {
    if (!show || !appId || !config) return
    const previousAppId = previous?.[1]
    const preserve =
      props.mode === 'edit' && props.schedule?.applicationId === appId
        ? props.schedule.parameters
        : previousAppId === appId
          ? form.parameters
          : {}
    form.parameters = createDefaultAutomationParameters(
      config.input_schema,
      preserve,
    )
  },
)

function changeDevice(value: AppOptionValue | null): void {
  const next = value as string | null
  if (next === form.deviceId) return
  form.deviceId = next
  form.applicationId = null
  form.parameters = {}
}

function changeApplication(value: AppOptionValue | null): void {
  form.applicationId = value as string | null
  form.parameters = {}
}

function localTimeToValue(value: string): number {
  const [hours, minutes] = value.split(':').map(Number)
  return new Date(2000, 0, 1, hours ?? 0, minutes ?? 0).getTime()
}

function valueToLocalTime(value: number): string {
  const date = new Date(value)
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function submit(): void {
  if (
    disabledReason.value ||
    !form.deviceId ||
    !form.applicationId ||
    form.localTimeValue === null
  ) {
    return
  }
  emit('submit', {
    name: form.name.trim(),
    deviceId: form.deviceId,
    applicationId: form.applicationId,
    parameters: { ...form.parameters },
    scheduleType: 'daily',
    localTime: valueToLocalTime(form.localTimeValue),
    timezone: form.timezone,
    enabled: form.enabled,
  })
}
</script>

<template>
  <FormDialog
    :show="show"
    :title="mode === 'create' ? '新建定时计划' : '编辑定时计划'"
    size="lg"
    :submitting="submitting"
    :submit-disabled="Boolean(disabledReason)"
    :submit-disabled-reason="disabledReason"
    @update:show="$emit('update:show', $event)"
    @submit="submit"
  >
    <NForm class="schedule-form" label-placement="top">
      <NFormItem label="计划名称" required>
        <AppInput v-model="form.name" placeholder="例如 每日商品发布" />
      </NFormItem>
      <NFormItem label="执行设备" required>
        <AppSelect
          :model-value="form.deviceId"
          :options="deviceOptions"
          :loading="deviceOptionsLoading"
          filterable
          placeholder="请选择设备"
          @update:model-value="changeDevice"
        />
      </NFormItem>
      <NFormItem label="执行类型">
        <AppInput model-value="影刀应用" disabled />
      </NFormItem>
      <NFormItem label="影刀应用" required>
        <AppSelect
          :model-value="form.applicationId"
          :options="applicationOptions"
          :loading="inventoryQuery.isPending.value"
          :disabled="!form.deviceId"
          filterable
          placeholder="请选择当前设备可访问的应用"
          @update:model-value="changeApplication"
        />
      </NFormItem>
      <NFormItem label="触发规则">
        <AppInput model-value="每天" disabled />
      </NFormItem>
      <NFormItem label="执行时间" required>
        <AppTimePicker v-model="form.localTimeValue" :clearable="false" />
      </NFormItem>
      <NFormItem label="时区" required>
        <AppSelect
          v-model="form.timezone"
          :options="timezoneOptions"
          filterable
          placeholder="请选择 IANA 时区"
        />
      </NFormItem>
      <NFormItem label="启用状态">
        <AppSwitch v-model="form.enabled" />
      </NFormItem>
      <section class="schedule-form__parameters">
        <h3>应用参数</h3>
        <p v-if="inventoryInitialError" class="schedule-form__error">
          影刀应用读取失败：{{ getErrorMessage(inventoryQuery.error.value) }}
        </p>
        <p v-else-if="configInitialError" class="schedule-form__error">
          参数配置读取失败：{{ getErrorMessage(configQuery.error.value) }}
        </p>
        <AutomationParameterFields
          v-model="form.parameters"
          :schema="schema"
          :disabled="configInitialLoading"
        />
        <p
          v-if="
            form.applicationId && !schema.fields.length && !configInitialLoading
          "
        >
          该应用没有配置输入参数。
        </p>
      </section>
    </NForm>
  </FormDialog>
</template>

<style scoped>
.schedule-form {
  display: grid;
  gap: 0 var(--space-4);
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.schedule-form__parameters {
  min-width: 0;
  grid-column: 1 / -1;
}

.schedule-form__parameters h3 {
  margin-bottom: var(--space-3);
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
}

.schedule-form__parameters p {
  color: var(--text-secondary);
}

.schedule-form__parameters .schedule-form__error {
  color: var(--color-error);
}

@media (max-width: 720px) {
  .schedule-form {
    grid-template-columns: 1fr;
  }

  .schedule-form__parameters {
    grid-column: auto;
  }
}
</style>
