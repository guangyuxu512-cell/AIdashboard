<script setup lang="ts">
import { NFormItem } from 'naive-ui'

import AppInput from '@/shared/ui/AppInput.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'
import type { AppOptionValue } from '@/shared/ui/types'

import type {
  CredentialFormErrors,
  CredentialFormValue,
} from '../model/credential-form'
import { VERIFICATION_CHANNEL_OPTIONS } from '../model/credential-form'

const props = withDefaults(
  defineProps<{
    modelValue: CredentialFormValue
    errors?: CredentialFormErrors
    configured?: boolean
    maskedIdentifier?: string | null
  }>(),
  {
    errors: () => ({}),
    configured: false,
    maskedIdentifier: null,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: CredentialFormValue]
}>()

function updateField<Key extends keyof CredentialFormValue>(
  key: Key,
  value: CredentialFormValue[Key],
): void {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

function updateVerificationChannel(value: AppOptionValue | null): void {
  if (value) {
    updateField(
      'preferredVerificationChannel',
      value as CredentialFormValue['preferredVerificationChannel'],
    )
  }
}
</script>

<template>
  <NFormItem
    label="登录账号"
    :validation-status="errors.loginIdentifier ? 'error' : undefined"
    :feedback="errors.loginIdentifier"
  >
    <div class="credential-form-field">
      <AppInput
        :model-value="modelValue.loginIdentifier"
        :maxlength="320"
        :placeholder="
          configured
            ? '留空保留当前登录账号'
            : '手机号、邮箱、用户名或账号 ID'
        "
        @update:model-value="updateField('loginIdentifier', $event)"
      />
      <span v-if="configured && maskedIdentifier">
        当前账号：{{ maskedIdentifier }}
      </span>
    </div>
  </NFormItem>
  <NFormItem
    label="登录密码"
    :validation-status="errors.password ? 'error' : undefined"
    :feedback="errors.password"
  >
    <div class="credential-form-field">
      <AppInput
        :model-value="modelValue.password"
        type="password"
        :maxlength="1000"
        :placeholder="configured ? '留空表示不修改现有密码' : '请输入登录密码'"
        @update:model-value="updateField('password', $event)"
      />
      <span v-if="configured">密码不会从服务器回显。</span>
    </div>
  </NFormItem>
  <NFormItem
    label="首选验证码方式"
    :validation-status="
      errors.preferredVerificationChannel ? 'error' : undefined
    "
    :feedback="errors.preferredVerificationChannel"
  >
    <AppSelect
      :model-value="modelValue.preferredVerificationChannel"
      :options="VERIFICATION_CHANNEL_OPTIONS"
      @update:model-value="updateVerificationChannel"
    />
  </NFormItem>
</template>

<style scoped>
.credential-form-field {
  display: flex;
  width: 100%;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-1);
}

.credential-form-field span {
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
}
</style>
