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
import { useBusinessSkillCatalogQuery } from '@/entities/business-skill'
import { useDeviceProviderInventoriesQuery } from '@/entities/device'
import type {
  ScheduleDetailViewModel,
  ScheduleExecutionTypeDto,
  ScheduleSaveInput,
} from '@/entities/schedule'
import { getErrorMessage } from '@/shared/api'
import FormDialog from '@/shared/components/FormDialog.vue'
import SchemaParameterFields from '@/shared/components/SchemaParameterFields.vue'
import { AppInput, AppSelect, AppSwitch, AppTimePicker } from '@/shared/ui'
import type { AppOptionValue } from '@/shared/ui/types'
import {
  createDefaultSchemaParameters,
  validateSchemaParameters,
} from '@/shared/utils/schema-parameters'
import {
  createTimezoneOptions,
  filterTimezoneOption,
  getBrowserTimezone,
} from '@/shared/utils/timezones'

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

const currentTimezone = getBrowserTimezone()
const executionTypeOptions: SelectOption[] = [
  { label: '影刀应用', value: 'yingdao_application' },
  { label: '业务 Skill', value: 'business_skill' },
]
const form = reactive({
  name: '',
  deviceId: null as string | null,
  executionType: 'yingdao_application' as ScheduleExecutionTypeDto,
  applicationId: null as string | null,
  skillId: null as string | null,
  localTimeValue: null as number | null,
  timezone: currentTimezone,
  enabled: true,
  parameters: {} as Record<string, unknown>,
})
const initializedKey = ref('')
const parameterSourceKey = ref('')
const isYingdao = computed(
  () => form.executionType === 'yingdao_application',
)
const isBusinessSkill = computed(
  () => form.executionType === 'business_skill',
)
const inventoryQuery = useDeviceProviderInventoriesQuery(
  computed(() => form.deviceId),
  isYingdao,
)
const applicationId = computed(() => form.applicationId)
const configQuery = useAutomationApplicationConfigQuery(
  applicationId,
  isYingdao,
)
const businessSkillQuery = useBusinessSkillCatalogQuery(
  computed(() => form.deviceId),
  isBusinessSkill,
)
const applicationSchema = computed(
  () => configQuery.data.value?.input_schema ?? { fields: [] },
)
const applications = computed(
  () => inventoryQuery.data.value?.applications ?? [],
)
const businessSkills = computed(() => businessSkillQuery.data.value ?? [])
const selectedBusinessSkill = computed(() =>
  businessSkills.value.find((skill) => skill.skillId === form.skillId),
)
const timezoneOptions = computed(() =>
  createTimezoneOptions([form.timezone, props.schedule?.timezone ?? '']),
)
const inventoryHasData = computed(() => inventoryQuery.data.value !== undefined)
const inventoryInitialError = computed(
  () => Boolean(inventoryQuery.error.value) && !inventoryHasData.value,
)
const businessSkillHasData = computed(
  () => businessSkillQuery.data.value !== undefined,
)
const businessSkillInitialError = computed(
  () => Boolean(businessSkillQuery.error.value) && !businessSkillHasData.value,
)
const applicationOptions = computed<SelectOption[]>(() => {
  const options = applications.value.map((application) => ({
    label: application.appName,
    value: application.appId,
  }))
  if (
    props.schedule?.executionType === 'yingdao_application' &&
    form.applicationId === props.schedule.applicationId &&
    form.applicationId &&
    !options.some((option) => option.value === form.applicationId)
  ) {
    options.unshift({
      label: props.schedule.executionName,
      value: form.applicationId,
    })
  }
  return options
})
const businessSkillOptions = computed<SelectOption[]>(() => {
  const options = businessSkills.value.map((skill) => ({
    label: skill.configurable
      ? skill.displayName
      : `${skill.displayName}（${skill.unavailableReason ?? '暂不可配置'}）`,
    value: skill.skillId,
    disabled: !skill.configurable,
  }))
  if (
    props.schedule?.executionType === 'business_skill' &&
    form.skillId === props.schedule.skillId &&
    form.skillId &&
    !options.some((option) => option.value === form.skillId)
  ) {
    options.unshift({
      label: `${props.schedule.executionName}（当前设备已不可用）`,
      value: form.skillId,
      disabled: true,
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
  if (isYingdao.value) {
    if (!form.applicationId) return '请选择影刀应用'
    if (inventoryInitialError.value) return '设备影刀应用读取失败'
    if (configInitialLoading.value) return '正在读取应用参数配置'
    if (configInitialError.value) return '应用参数配置读取失败'
    const error = validateAutomationParameters(
      applicationSchema.value,
      form.parameters,
    )
    if (error) return error
  } else {
    if (businessSkillInitialError.value) return '业务 Skill 读取失败'
    if (!form.skillId) return '请选择业务 Skill'
    if (!selectedBusinessSkill.value) return '该业务 Skill 当前已不可用'
    if (!selectedBusinessSkill.value.configurable) {
      return (
        selectedBusinessSkill.value.unavailableReason ??
        '该业务 Skill 暂时无法配置'
      )
    }
    const error = validateSchemaParameters(
      selectedBusinessSkill.value.parameterFields,
      form.parameters,
    )
    if (error) return error
  }
  if (form.localTimeValue === null) return '请选择每日执行时间'
  if (!form.timezone) return '请选择时区'
  return null
})

watch(
  [() => props.show, () => props.mode, () => props.schedule],
  ([show, mode, schedule]) => {
    if (!show) {
      initializedKey.value = ''
      parameterSourceKey.value = ''
      return
    }
    const key =
      mode === 'edit' ? `edit:${schedule?.scheduleId ?? ''}` : 'create'
    if (key === initializedKey.value || (mode === 'edit' && !schedule)) return
    initializedKey.value = key
    parameterSourceKey.value = ''
    form.name = schedule?.name ?? ''
    form.deviceId = schedule?.deviceId ?? null
    form.executionType = schedule?.executionType ?? 'yingdao_application'
    form.applicationId = schedule?.applicationId ?? null
    form.skillId =
      schedule?.executionType === 'business_skill' ? schedule.skillId : null
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
  [
    () => props.show,
    () => form.executionType,
    () => form.applicationId,
    () => configQuery.data.value,
    () => form.skillId,
    () => selectedBusinessSkill.value,
  ],
  ([show, executionType, appId, config, skillId, skill]) => {
    if (!show) return
    const sourceKey =
      executionType === 'yingdao_application'
        ? appId && config
          ? `yingdao:${appId}`
          : ''
        : skillId && skill?.configurable
          ? `business:${skillId}`
          : ''
    if (!sourceKey || sourceKey === parameterSourceKey.value) return
    const editingCurrentTarget =
      props.mode === 'edit' &&
      props.schedule?.executionType === executionType &&
      (executionType === 'yingdao_application'
        ? props.schedule.applicationId === appId
        : props.schedule.skillId === skillId)
    const existing = editingCurrentTarget ? props.schedule.parameters : {}
    form.parameters =
      executionType === 'yingdao_application' && config
        ? createDefaultAutomationParameters(config.input_schema, existing)
        : createDefaultSchemaParameters(skill?.parameterFields ?? [], existing)
    parameterSourceKey.value = sourceKey
  },
)

function changeDevice(value: AppOptionValue | null): void {
  const next = value as string | null
  if (next === form.deviceId) return
  form.deviceId = next
  resetTarget()
}

function changeExecutionType(value: AppOptionValue | null): void {
  if (value !== 'yingdao_application' && value !== 'business_skill') return
  if (value === form.executionType) return
  form.executionType = value
  resetTarget()
}

function changeApplication(value: AppOptionValue | null): void {
  form.applicationId = value as string | null
  form.parameters = {}
  parameterSourceKey.value = ''
}

function changeBusinessSkill(value: AppOptionValue | null): void {
  form.skillId = value as string | null
  form.parameters = {}
  parameterSourceKey.value = ''
}

function resetTarget(): void {
  form.applicationId = null
  form.skillId = null
  form.parameters = {}
  parameterSourceKey.value = ''
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
    form.localTimeValue === null
  ) {
    return
  }
  emit('submit', {
    name: form.name.trim(),
    deviceId: form.deviceId,
    executionType: form.executionType,
    applicationId: isYingdao.value ? form.applicationId : null,
    skillId: isBusinessSkill.value ? form.skillId : null,
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
      <NFormItem label="执行类型" required>
        <AppSelect
          :model-value="form.executionType"
          :options="executionTypeOptions"
          @update:model-value="changeExecutionType"
        />
      </NFormItem>
      <NFormItem v-if="isYingdao" label="影刀应用" required>
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
      <NFormItem v-else label="业务 Skill" required>
        <AppSelect
          :model-value="form.skillId"
          :options="businessSkillOptions"
          :loading="businessSkillQuery.isPending.value"
          :disabled="!form.deviceId"
          filterable
          :placeholder="
            businessSkillHasData && !businessSkills.length
              ? '当前 Worker 尚未安装业务 Skill'
              : '请选择当前设备可用的业务 Skill'
          "
          @update:model-value="changeBusinessSkill"
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
          :filter="filterTimezoneOption"
          filterable
          placeholder="请选择时区"
        />
      </NFormItem>
      <NFormItem label="启用状态">
        <AppSwitch v-model="form.enabled" />
      </NFormItem>
      <section class="schedule-form__parameters">
        <h3>{{ isYingdao ? '应用参数' : 'Skill 参数' }}</h3>
        <template v-if="isYingdao">
          <p v-if="inventoryInitialError" class="schedule-form__error">
            影刀应用读取失败：{{ getErrorMessage(inventoryQuery.error.value) }}
          </p>
          <p v-else-if="configInitialError" class="schedule-form__error">
            参数配置读取失败：{{ getErrorMessage(configQuery.error.value) }}
          </p>
          <AutomationParameterFields
            v-model="form.parameters"
            :schema="applicationSchema"
            :disabled="configInitialLoading"
          />
          <p
            v-if="
              form.applicationId &&
              !applicationSchema.fields.length &&
              !configInitialLoading
            "
          >
            该应用没有配置输入参数。
          </p>
        </template>
        <template v-else>
          <p v-if="businessSkillInitialError" class="schedule-form__error">
            业务 Skill 读取失败：{{
              getErrorMessage(businessSkillQuery.error.value)
            }}
          </p>
          <p v-else-if="businessSkillHasData && !businessSkills.length">
            暂无业务 Skill。当前 Worker 尚未安装业务 Skill。
          </p>
          <p
            v-else-if="selectedBusinessSkill && !selectedBusinessSkill.configurable"
            class="schedule-form__error"
          >
            {{ selectedBusinessSkill.unavailableReason }}
          </p>
          <SchemaParameterFields
            v-else-if="selectedBusinessSkill"
            v-model="form.parameters"
            :fields="selectedBusinessSkill.parameterFields"
          />
          <p
            v-if="
              selectedBusinessSkill?.configurable &&
              !selectedBusinessSkill.parameterFields.length
            "
          >
            该业务 Skill 不需要输入参数。
          </p>
        </template>
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
