<script setup lang="ts">
import { computed, watch } from 'vue'
import { NForm } from 'naive-ui'
import { useForm } from 'vee-validate'

import type { CredentialStatusViewModel } from '@/entities/credential'
import FormDialog from '@/shared/components/FormDialog.vue'

import {
  createCredentialFormSchema,
  EMPTY_CREDENTIAL_FORM,
  type CredentialFormValue,
} from '../model/credential-form'
import CredentialFormFields from './CredentialFormFields.vue'

export type { CredentialFormValue } from '../model/credential-form'

const props = defineProps<{
  show: boolean
  credential: CredentialStatusViewModel | null
  submitting?: boolean
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  save: [value: CredentialFormValue]
}>()

const { defineField, errors, handleSubmit, resetForm, setErrors } =
  useForm<CredentialFormValue>({ initialValues: EMPTY_CREDENTIAL_FORM })
const [loginIdentifier] = defineField('loginIdentifier')
const [password] = defineField('password')
const [preferredVerificationChannel] = defineField(
  'preferredVerificationChannel',
)

const configured = computed(() => props.credential?.configured ?? false)
const title = computed(() =>
  configured.value ? '更新账号与连接' : '配置账号与连接',
)
const formValue = computed<CredentialFormValue>({
  get: () => ({
    loginIdentifier: loginIdentifier.value,
    password: password.value,
    preferredVerificationChannel: preferredVerificationChannel.value,
  }),
  set: (value) => {
    loginIdentifier.value = value.loginIdentifier
    password.value = value.password
    preferredVerificationChannel.value = value.preferredVerificationChannel
  },
})

watch(
  () => props.show,
  (show) => {
    resetForm({
      values: {
        ...EMPTY_CREDENTIAL_FORM,
        preferredVerificationChannel: show
          ? (props.credential?.preferredVerificationChannel ?? 'manual')
          : 'manual',
      },
    })
  },
)

const submit = handleSubmit((values) => {
  const parsed = createCredentialFormSchema(configured.value).safeParse(values)
  const fieldErrors = parsed.success ? {} : parsed.error.flatten().fieldErrors
  if (!parsed.success) {
    setErrors({
      loginIdentifier: fieldErrors.loginIdentifier?.[0],
      password: fieldErrors.password?.[0],
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
      <CredentialFormFields
        v-model="formValue"
        :errors="errors"
        :configured="configured"
        :masked-identifier="credential?.maskedIdentifier"
      />
    </NForm>
  </FormDialog>
</template>
