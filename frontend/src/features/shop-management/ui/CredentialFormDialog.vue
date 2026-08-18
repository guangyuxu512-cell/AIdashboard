<script setup lang="ts">
import { computed, watch } from 'vue'
import { NForm, NFormItem } from 'naive-ui'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import type {
  CredentialStatusViewModel,
  VerificationChannel,
} from '@/entities/credential'
import FormDialog from '@/shared/components/FormDialog.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'
import type { AppOptionValue } from '@/shared/ui/types'

export interface CredentialFormValue {
  loginIdentifier: string
  password: string
  preferredVerificationChannel: VerificationChannel
}

const props = defineProps<{
  show: boolean
  credential: CredentialStatusViewModel | null
  submitting?: boolean
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  save: [value: CredentialFormValue]
}>()

const verificationChannelOptions = [
  { label: '人工', value: 'manual' },
  { label: '邮箱', value: 'email' },
  { label: '短信硬件', value: 'sms_hardware' },
]

const emptyForm: CredentialFormValue = {
  loginIdentifier: '',
  password: '',
  preferredVerificationChannel: 'manual',
}

const formSchema = z.object({
  loginIdentifier: z.string().trim().max(320, '登录账号最多 320 个字符'),
  password: z.string().max(1000, '登录密码最多 1000 个字符'),
  preferredVerificationChannel: z.enum(['manual', 'email', 'sms_hardware']),
})

const { defineField, errors, handleSubmit, resetForm, setErrors } =
  useForm<CredentialFormValue>({ initialValues: emptyForm })
const [loginIdentifier] = defineField('loginIdentifier')
const [password] = defineField('password')
const [preferredVerificationChannel] = defineField(
  'preferredVerificationChannel',
)

const configured = computed(() => props.credential?.configured ?? false)
const title = computed(() =>
  configured.value ? '更新账号与连接' : '配置账号与连接',
)

watch(
  () => props.show,
  (show) => {
    resetForm({
      values: {
        ...emptyForm,
        preferredVerificationChannel: show
          ? (props.credential?.preferredVerificationChannel ?? 'manual')
          : 'manual',
      },
    })
  },
)

function updateVerificationChannel(value: AppOptionValue | null): void {
  preferredVerificationChannel.value = value as VerificationChannel
}

const submit = handleSubmit((values) => {
  const parsed = formSchema.safeParse(values)
  const fieldErrors = parsed.success ? {} : parsed.error.flatten().fieldErrors
  const loginError =
    !configured.value && !values.loginIdentifier.trim()
      ? '请输入登录账号'
      : fieldErrors.loginIdentifier?.[0]
  const passwordError =
    !configured.value && !values.password
      ? '请输入登录密码'
      : fieldErrors.password?.[0]

  if (!parsed.success || loginError || passwordError) {
    setErrors({
      loginIdentifier: loginError,
      password: passwordError,
      preferredVerificationChannel:
        fieldErrors.preferredVerificationChannel?.[0],
    })
    return
  }

  emit('save', parsed.data)
  password.value = ''
})
</script>

<template>
  <FormDialog
    :show="show"
    :title="title"
    size="sm"
    :submitting="submitting"
    @update:show="$emit('update:show', $event)"
    @submit="submit"
    @cancel="$emit('update:show', false)"
  >
    <NForm label-placement="top" @submit.prevent="submit">
      <NFormItem
        label="登录账号"
        :validation-status="errors.loginIdentifier ? 'error' : undefined"
        :feedback="errors.loginIdentifier"
      >
        <div class="credential-form__field">
          <AppInput
            v-model="loginIdentifier"
            :maxlength="320"
            :placeholder="
              configured
                ? '留空保留当前登录账号'
                : '手机号、邮箱、用户名或账号 ID'
            "
          />
          <span v-if="configured && credential?.maskedIdentifier">
            当前账号：{{ credential.maskedIdentifier }}
          </span>
        </div>
      </NFormItem>
      <NFormItem
        label="登录密码"
        :validation-status="errors.password ? 'error' : undefined"
        :feedback="errors.password"
      >
        <div class="credential-form__field">
          <AppInput
            v-model="password"
            type="password"
            :maxlength="1000"
            :placeholder="
              configured ? '留空表示不修改现有密码' : '请输入登录密码'
            "
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
          :model-value="preferredVerificationChannel"
          :options="verificationChannelOptions"
          @update:model-value="updateVerificationChannel"
        />
      </NFormItem>
    </NForm>
  </FormDialog>
</template>

<style scoped>
.credential-form__field {
  display: flex;
  width: 100%;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-1);
}

.credential-form__field span {
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
}
</style>
