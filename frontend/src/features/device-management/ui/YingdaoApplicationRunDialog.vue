<script setup lang="ts">
import { NForm, NFormItem, useMessage } from 'naive-ui'
import { computed, ref, watch } from 'vue'

import {
  useAutomationApplicationConfigQuery,
  AutomationParameterFields,
  createDefaultAutomationParameters,
  validateAutomationParameters,
} from '@/entities/automation-application'
import type { ProviderApplicationViewModel } from '@/entities/device'
import { ShopSelector } from '@/entities/shop'
import { useCreateTaskMutation } from '@/entities/task'
import { getErrorMessage } from '@/shared/api'
import { AppDialog } from '@/shared/ui'

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
const shopId = ref<string | null>(null)
const params = ref<Record<string, unknown>>({})
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
  if (!shopId.value) return '请选择本次任务使用的店铺账号'
  if (configInitialLoading.value) return '正在读取参数配置'
  if (configInitialError.value) return '参数配置加载失败，暂时无法运行'
  const schema = configQuery.data.value?.input_schema ?? { fields: [] }
  return validateAutomationParameters(schema, params.value)
})

watch(
  [() => props.show, () => configQuery.data.value],
  ([show, config]) => {
    if (!show) return
    params.value = createDefaultAutomationParameters(
      config?.input_schema ?? { fields: [] },
    )
  },
  { immediate: true },
)

watch(
  () => props.show,
  (show) => {
    if (show) shopId.value = null
  },
  { immediate: true },
)

async function run(): Promise<void> {
  if (!props.application || !props.deviceId || !shopId.value) return
  if (runDisabledReason.value) {
    message.error(runDisabledReason.value)
    return
  }
  const schema = configQuery.data.value?.input_schema ?? { fields: [] }
  const validationError = validateAutomationParameters(schema, params.value)
  if (validationError) {
    message.error(validationError)
    return
  }
  try {
    const task = await createTask.mutateAsync({
      target_device_id: props.deviceId,
      shop_id: shopId.value,
      skill_id: 'yingdao.app.run',
      input: { app_id: props.application.appId, params: { ...params.value } },
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
      <NFormItem label="店铺账号" required>
        <ShopSelector v-model="shopId" />
      </NFormItem>
      <AutomationParameterFields
        v-model="params"
        :schema="configQuery.data.value?.input_schema ?? { fields: [] }"
      />
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
