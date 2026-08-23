<script setup lang="ts">
import { NForm, NFormItem, useMessage } from 'naive-ui'
import { computed, reactive, watch } from 'vue'

import {
  useAutomationApplicationConfigQuery,
  validateAutomationParameters,
} from '@/entities/automation-application'
import type { ProviderApplicationViewModel } from '@/entities/device'
import { useCreateTaskMutation } from '@/entities/task'
import { getErrorMessage } from '@/shared/api'
import { AppDialog, AppInput, AppNumberInput, AppSelect, AppSwitch } from '@/shared/ui'

const props = defineProps<{
  show: boolean
  application: ProviderApplicationViewModel | null
  deviceId: string | null
}>()
const emit = defineEmits<{
  'update:show': [value: boolean]
  started: [taskId: string]
}>()
const message = useMessage()
const appId = computed(() => props.application?.appId ?? null)
const configQuery = useAutomationApplicationConfigQuery(appId)
const createTask = useCreateTaskMutation()
const params = reactive<Record<string, unknown>>({})
const hasConfigData = computed(() => configQuery.data.value !== undefined)
const configInitialLoading = computed(
  () => configQuery.isPending.value && !hasConfigData.value,
)
const configInitialError = computed(
  () => Boolean(configQuery.error.value) && !hasConfigData.value,
)
const runDisabledReason = computed(() => {
  if (!props.application) return '当前 Application 不可用'
  if (!props.deviceId) return '当前未选择目标设备'
  if (configInitialLoading.value) return '正在读取参数配置'
  if (configInitialError.value) return '参数配置加载失败，暂时无法运行'
  const schema = configQuery.data.value?.input_schema ?? { fields: [] }
  return validateAutomationParameters(schema, params)
})

watch(
  [() => props.show, () => configQuery.data.value],
  ([show, config]) => {
    if (!show) return
    for (const key of Object.keys(params)) delete params[key]
    for (const field of config?.input_schema.fields ?? []) {
      if (field.default_value !== null) params[field.name] = field.default_value
    }
  },
  { immediate: true },
)

async function run(): Promise<void> {
  if (!props.application || !props.deviceId) return
  if (runDisabledReason.value) {
    message.error(runDisabledReason.value)
    return
  }
  const schema = configQuery.data.value?.input_schema ?? { fields: [] }
  const validationError = validateAutomationParameters(schema, params)
  if (validationError) {
    message.error(validationError)
    return
  }
  try {
    const task = await createTask.mutateAsync({
      target_device_id: props.deviceId,
      skill_id: 'yingdao.app.run',
      input: { app_id: props.application.appId, params: { ...params } },
    })
    message.success('影刀应用任务已创建')
    emit('update:show', false)
    emit('started', task.task_id)
  } catch (error) {
    message.error(getErrorMessage(error))
  }
}
</script>

<template>
  <AppDialog
    :show="show"
    :title="`运行应用 · ${application?.appName ?? ''}`"
    positive-text="运行"
    :loading="createTask.isPending.value || configInitialLoading"
    :positive-disabled="Boolean(runDisabledReason)"
    :positive-disabled-reason="runDisabledReason"
    @update:show="$emit('update:show', $event)"
    @confirm="run"
  >
    <NForm label-placement="top">
      <NFormItem
        v-for="field in configQuery.data.value?.input_schema.fields ?? []"
        :key="field.name"
        :label="field.label"
        :required="field.required"
      >
        <AppNumberInput
          v-if="field.type === 'number'"
          :model-value="params[field.name] as number"
          clearable
          @update:model-value="params[field.name] = $event"
        />
        <AppSwitch
          v-else-if="field.type === 'boolean'"
          :model-value="(params[field.name] as boolean) ?? false"
          @update:model-value="params[field.name] = $event"
        />
        <AppSelect
          v-else-if="field.type === 'select'"
          :model-value="params[field.name] as string"
          :options="field.options.map((value) => ({ label: value, value }))"
          clearable
          @update:model-value="params[field.name] = $event"
        />
        <AppInput
          v-else
          :model-value="params[field.name] as string"
          clearable
          @update:model-value="params[field.name] = $event"
        />
      </NFormItem>
    </NForm>
    <p v-if="configInitialError" class="application-run__error">
      参数配置加载失败：{{ getErrorMessage(configQuery.error.value) }}
    </p>
    <p v-if="!configQuery.data.value?.input_schema.fields.length">
      该应用没有配置输入参数，将直接创建运行任务。
    </p>
  </AppDialog>
</template>

<style scoped>
.application-run__error {
  color: var(--color-error);
}
</style>
