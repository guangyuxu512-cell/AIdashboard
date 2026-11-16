<script setup lang="ts">
import type { SelectOption } from 'naive-ui'
import { NCheckbox, NCheckboxGroup, NForm, NFormItem } from 'naive-ui'
import { computed, reactive, ref, watch } from 'vue'

import { useBusinessSkillCatalogQuery } from '@/entities/business-skill'
import { useDeviceLocalShopsQuery } from '@/entities/device'
import { ShopMultiSelector } from '@/entities/shop'
import type { ScheduleDetailViewModel, ScheduleSaveInput, ScheduleTypeDto } from '@/entities/schedule'
import { getErrorMessage } from '@/shared/api'
import FormDialog from '@/shared/components/FormDialog.vue'
import SchemaParameterFields from '@/shared/components/SchemaParameterFields.vue'
import { AppDatePicker, AppInput, AppRadio, AppSelect, AppSwitch, AppTimePicker } from '@/shared/ui'
import type { AppOptionValue } from '@/shared/ui/types'
import { createDefaultSchemaParameters, validateSchemaParameters } from '@/shared/utils/schema-parameters'
import { createTimezoneOptions, filterTimezoneOption, getBrowserTimezone } from '@/shared/utils/timezones'

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
const scheduleTypes = [
  { label: '一次', value: 'once' },
  { label: '每天', value: 'daily' },
  { label: '每周', value: 'weekly' },
]
const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
  .map((label, index) => ({ label, value: index + 1 }))
const form = reactive({
  name: '', deviceId: null as string | null, shopIds: [] as string[],
  skillId: null as string | null, parameters: {} as Record<string, unknown>,
  scheduleType: 'daily' as ScheduleTypeDto, localDateValue: null as number | null,
  weekdays: [] as number[], localTimeValue: null as number | null,
  timezone: currentTimezone, enabled: false,
})
const initializedKey = ref('')
const parameterSourceKey = ref('')
const shopsQuery = useDeviceLocalShopsQuery(computed(() => form.deviceId))
const shopOptions = computed(() => (shopsQuery.data.value?.shops ?? []).map((shop) => ({
  label: shop.shop_name, value: shop.local_shop_id,
  disabled: !shopsQuery.data.value?.available,
})))
const skillQuery = useBusinessSkillCatalogQuery(computed(() => form.deviceId), true)
const skills = computed(() => skillQuery.data.value ?? [])
const selectedSkill = computed(() => skills.value.find((skill) => skill.skillId === form.skillId))
const skillOptions = computed<SelectOption[]>(() => skills.value.map((skill) => ({
  label: skill.configurable ? skill.displayName : `${skill.displayName}（${skill.unavailableReason ?? '暂不可配置'}）`,
  value: skill.skillId, disabled: !skill.configurable,
})))
const timezoneOptions = computed(() => createTimezoneOptions([form.timezone, props.schedule?.timezone ?? '']))
const disabledReason = computed(() => {
  if (!form.name.trim()) return '请填写计划名称'
  if (!form.deviceId) return '请选择执行设备'
  if (props.schedule?.executionType === 'yingdao_application') return '旧影刀计划已停用，请新建 Worker 技能计划'
  if (skillQuery.error.value && !skillQuery.data.value) return '设备技能读取失败'
  if (!form.skillId) return '请选择 Worker 技能'
  if (!selectedSkill.value?.configurable) return selectedSkill.value?.unavailableReason ?? '该技能当前不可用'
  const error = validateSchemaParameters(selectedSkill.value.parameterFields, form.parameters)
  if (error) return error
  if (form.shopIds.length && !shopsQuery.data.value?.available) return '本机店铺清单暂不可用'
  if (form.scheduleType === 'once' && form.localDateValue === null) return '请选择一次执行日期'
  if (form.scheduleType === 'weekly' && !form.weekdays.length) return '请选择每周执行日'
  if (form.localTimeValue === null) return '请选择执行时间'
  if (!form.timezone) return '请选择时区'
  return null
})
function timeValue(value: string): number {
  const [hour, minute] = value.split(':').map(Number)
  return new Date(2000, 0, 1, hour ?? 0, minute ?? 0).getTime()
}
function dateValue(value: string): number {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year ?? 0, (month ?? 1) - 1, day ?? 1).getTime()
}
watch([() => props.show, () => props.mode, () => props.schedule], ([show, mode, schedule]) => {
  if (!show) { initializedKey.value = ''; parameterSourceKey.value = ''; return }
  const key = mode === 'edit' ? `edit:${schedule?.scheduleId ?? ''}` : 'create'
  if (key === initializedKey.value || (mode === 'edit' && !schedule)) return
  initializedKey.value = key
  parameterSourceKey.value = ''
  form.name = schedule?.name ?? ''
  form.deviceId = schedule?.deviceId ?? null
  form.shopIds = [...(schedule?.shopIds ?? [])]
  form.skillId = schedule?.executionType === 'business_skill' ? schedule.skillId : null
  form.parameters = { ...(schedule?.parameters ?? {}) }
  form.scheduleType = schedule?.scheduleType ?? 'daily'
  form.localDateValue = schedule?.localDate ? dateValue(schedule.localDate) : null
  form.weekdays = [...(schedule?.weekdays ?? [])]
  form.localTimeValue = timeValue(schedule?.localTime ?? '09:00')
  form.timezone = schedule?.timezone ?? currentTimezone
  form.enabled = schedule?.enabled ?? false
}, { immediate: true })
watch([() => props.show, () => form.skillId, selectedSkill], ([show, id, skill]) => {
  if (!show || !id || !skill?.configurable || parameterSourceKey.value === id) return
  const existing = props.mode === 'edit' && props.schedule?.skillId === id ? props.schedule.parameters : {}
  form.parameters = createDefaultSchemaParameters(skill.parameterFields, existing)
  parameterSourceKey.value = id
})
function changeDevice(value: AppOptionValue | null): void {
  const next = value as string | null
  if (next === form.deviceId) return
  form.deviceId = next
  form.shopIds = []
  form.skillId = null
  form.parameters = {}
  parameterSourceKey.value = ''
}
function changeSkill(value: AppOptionValue | null): void {
  form.skillId = value as string | null
  form.parameters = {}
  parameterSourceKey.value = ''
}
function changeScheduleType(value: AppOptionValue | null): void {
  if (value !== 'once' && value !== 'daily' && value !== 'weekly') return
  form.scheduleType = value
  if (value !== 'once') form.localDateValue = null
  if (value !== 'weekly') form.weekdays = []
}
function submit(): void {
  if (disabledReason.value || !form.deviceId || form.localTimeValue === null) return
  const time = new Date(form.localTimeValue)
  const date = form.localDateValue === null ? null : new Date(form.localDateValue)
  const pad = (n: number) => String(n).padStart(2, '0')
  emit('submit', {
    name: form.name.trim(), deviceId: form.deviceId, shopIds: [...form.shopIds],
    executionType: 'business_skill', applicationId: null, parameterPresetId: null,
    skillId: form.skillId, parameters: { ...form.parameters }, scheduleType: form.scheduleType,
    localTime: `${pad(time.getHours())}:${pad(time.getMinutes())}`, timezone: form.timezone,
    localDate: form.scheduleType === 'once' && date ? `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` : null,
    weekdays: form.scheduleType === 'weekly' ? [...form.weekdays] : [], enabled: form.enabled,
  })
}
</script>

<template>
  <FormDialog :show="show" :title="mode === 'create' ? '新建定时计划' : '编辑定时计划'"
    size="lg" :submitting="submitting" :submit-disabled="Boolean(disabledReason)"
    :submit-disabled-reason="disabledReason" @update:show="$emit('update:show', $event)" @submit="submit">
    <NForm class="schedule-form" label-placement="top">
      <NFormItem label="计划名称" required><AppInput v-model="form.name" /></NFormItem>
      <NFormItem label="执行设备" required>
        <AppSelect :model-value="form.deviceId" :options="deviceOptions" :loading="deviceOptionsLoading"
          filterable placeholder="请选择设备" @update:model-value="changeDevice" />
      </NFormItem>
      <NFormItem label="设备上报的本机店铺（可选）">
        <ShopMultiSelector v-model="form.shopIds" :options="shopOptions"
          :loading="shopsQuery.isPending.value" :disabled="!form.deviceId || !shopsQuery.data.value?.available" />
      </NFormItem>
      <NFormItem label="Worker 技能" required>
        <AppSelect :model-value="form.skillId" :options="skillOptions" :loading="skillQuery.isPending.value"
          :disabled="!form.deviceId" filterable placeholder="请选择当前设备可用的技能" @update:model-value="changeSkill" />
      </NFormItem>
      <NFormItem label="触发规则" required><AppRadio :model-value="form.scheduleType" :options="scheduleTypes" @update:model-value="changeScheduleType" /></NFormItem>
      <NFormItem v-if="form.scheduleType === 'once'" label="执行日期" required><AppDatePicker v-model="form.localDateValue" :clearable="false" /></NFormItem>
      <NFormItem v-if="form.scheduleType === 'weekly'" label="每周执行日" required>
        <NCheckboxGroup v-model:value="form.weekdays" class="schedule-form__weekdays">
          <NCheckbox v-for="weekday in weekdays" :key="weekday.value" :value="weekday.value" :label="weekday.label" />
        </NCheckboxGroup>
      </NFormItem>
      <NFormItem label="执行时间" required><AppTimePicker v-model="form.localTimeValue" :clearable="false" /></NFormItem>
      <NFormItem label="时区" required><AppSelect v-model="form.timezone" :options="timezoneOptions" :filter="filterTimezoneOption" filterable /></NFormItem>
      <NFormItem label="启用状态"><AppSwitch v-model="form.enabled" /></NFormItem>
      <section class="schedule-form__parameters">
        <h3>技能参数</h3>
        <p v-if="skillQuery.error.value && !skillQuery.data.value">技能读取失败：{{ getErrorMessage(skillQuery.error.value) }}</p>
        <SchemaParameterFields v-else-if="selectedSkill" v-model="form.parameters" :fields="selectedSkill.parameterFields" />
      </section>
    </NForm>
  </FormDialog>
</template>

<style scoped>
.schedule-form { display: grid; gap: 0 var(--space-4); grid-template-columns: repeat(2, minmax(0, 1fr)); }
.schedule-form__parameters { min-width: 0; grid-column: 1 / -1; }
.schedule-form__weekdays { display: flex; flex-wrap: wrap; gap: var(--space-2) var(--space-3); }
@media (max-width: 720px) { .schedule-form { grid-template-columns: 1fr; } }
</style>
