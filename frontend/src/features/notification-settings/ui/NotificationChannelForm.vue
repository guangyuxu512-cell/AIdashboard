<script setup lang="ts">
import { computed, watch } from 'vue'
import { NForm, NFormItem } from 'naive-ui'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import {
  NOTIFICATION_CHANNEL_TYPE_OPTIONS,
  type NotificationChannelSaveInput,
  type NotificationChannelViewModel,
} from '@/entities/notification-channel'
import AppButton from '@/shared/ui/AppButton.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'
import AppSwitch from '@/shared/ui/AppSwitch.vue'

const props = withDefaults(
  defineProps<{
    channel: NotificationChannelViewModel | null
    creating?: boolean
    saving?: boolean
    testing?: boolean
  }>(),
  { creating: false, saving: false, testing: false },
)

const emit = defineEmits<{
  save: [input: NotificationChannelSaveInput]
  test: []
}>()

const emptyForm: NotificationChannelSaveInput = {
  channelType: 'feishu_webhook',
  name: '',
  enabled: true,
  webhookUrl: '',
  deviceOfflineEnabled: true,
  deviceRecoveredEnabled: true,
}

const schema = z.object({
  channelType: z.enum(['feishu_webhook', 'wecom_webhook']),
  name: z.string().trim().min(1, '请输入通道名称').max(100),
  enabled: z.boolean(),
  webhookUrl: z.string().trim().max(2048),
  deviceOfflineEnabled: z.boolean(),
  deviceRecoveredEnabled: z.boolean(),
})

const { defineField, errors, handleSubmit, resetForm, setErrors } =
  useForm<NotificationChannelSaveInput>({ initialValues: emptyForm })
const [channelType] = defineField('channelType')
const [name] = defineField('name')
const [enabled] = defineField('enabled')
const [webhookUrl] = defineField('webhookUrl')
const [deviceOfflineEnabled] = defineField('deviceOfflineEnabled')
const [deviceRecoveredEnabled] = defineField('deviceRecoveredEnabled')

const webhookPlaceholder = computed(() =>
  props.channel?.webhookConfigured
    ? '已配置；留空将保留原 Webhook URL'
    : '请输入群机器人 Webhook URL',
)

watch(
  () => [props.channel, props.creating] as const,
  () => {
    resetForm({
      values: props.channel
        ? {
            channelType: props.channel.channelType,
            name: props.channel.name,
            enabled: props.channel.enabled,
            webhookUrl: '',
            deviceOfflineEnabled: props.channel.deviceOfflineEnabled,
            deviceRecoveredEnabled: props.channel.deviceRecoveredEnabled,
          }
        : { ...emptyForm },
    })
  },
  { immediate: true },
)

const submit = handleSubmit((values) => {
  const parsed = schema.safeParse(values)
  if (!parsed.success) {
    const fieldErrors = parsed.error.flatten().fieldErrors
    setErrors({
      channelType: fieldErrors.channelType?.[0],
      name: fieldErrors.name?.[0],
      webhookUrl: fieldErrors.webhookUrl?.[0],
    })
    return
  }
  if (!props.channel?.webhookConfigured && !parsed.data.webhookUrl) {
    setErrors({ webhookUrl: '首次配置必须填写 Webhook URL' })
    return
  }
  emit('save', parsed.data)
})
</script>

<template>
  <NForm label-placement="top" @submit.prevent="submit">
    <div class="notification-form__grid">
      <NFormItem label="通道类型" :feedback="errors.channelType">
        <AppSelect
          v-model="channelType"
          :options="[...NOTIFICATION_CHANNEL_TYPE_OPTIONS]"
          :disabled="Boolean(channel)"
        />
      </NFormItem>
      <NFormItem label="通道名称" :feedback="errors.name">
        <AppInput v-model="name" :maxlength="100" placeholder="例如：运营告警群" />
      </NFormItem>
    </div>

    <NFormItem
      label="Webhook URL"
      :validation-status="errors.webhookUrl ? 'error' : undefined"
      :feedback="errors.webhookUrl"
    >
      <AppInput
        v-model="webhookUrl"
        type="password"
        :maxlength="2048"
        :placeholder="webhookPlaceholder"
      />
    </NFormItem>
    <p class="notification-form__secret-hint">
      URL 仅在提交时使用，服务端加密保存，页面不会回显明文。
    </p>

    <div class="notification-form__switches">
      <label><span>启用通道</span><AppSwitch v-model="enabled" /></label>
      <label><span>设备离线通知</span><AppSwitch v-model="deviceOfflineEnabled" /></label>
      <label><span>设备恢复通知</span><AppSwitch v-model="deviceRecoveredEnabled" /></label>
    </div>

    <div class="notification-form__actions">
      <AppButton
        v-if="channel"
        :loading="testing"
        :disabled="saving"
        @click="$emit('test')"
      >
        发送测试通知
      </AppButton>
      <AppButton
        tone="primary"
        attr-type="submit"
        :loading="saving"
        :disabled="testing"
      >
        保存配置
      </AppButton>
    </div>
  </NForm>
</template>

<style scoped>
.notification-form__grid {
  display: grid;
  gap: var(--layout-card-gap);
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.notification-form__secret-hint {
  margin-top: calc(var(--space-2) * -1);
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
}

.notification-form__switches {
  display: grid;
  gap: var(--space-3);
  margin-top: var(--space-5);
}

.notification-form__switches label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  background: var(--bg-subtle);
}

.notification-form__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-5);
}

@media (max-width: 760px) {
  .notification-form__grid {
    grid-template-columns: 1fr;
  }
}
</style>
