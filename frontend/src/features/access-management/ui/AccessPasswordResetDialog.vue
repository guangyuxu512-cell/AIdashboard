<script setup lang="ts">
import { watch } from 'vue'
import { NForm, NFormItem } from 'naive-ui'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import FormDialog from '@/shared/components/FormDialog.vue'
import AppInput from '@/shared/ui/AppInput.vue'

const props = defineProps<{ show: boolean; submitting?: boolean }>()
const emit = defineEmits<{
  'update:show': [value: boolean]
  save: [password: string]
}>()

interface PasswordFormValues {
  password: string
  confirmation: string
}

const { defineField, errors, handleSubmit, resetForm, setErrors } =
  useForm<PasswordFormValues>({
    initialValues: { password: '', confirmation: '' },
  })
const [password] = defineField('password')
const [confirmation] = defineField('confirmation')

watch(
  () => props.show,
  (show) => {
    if (show) resetForm({ values: { password: '', confirmation: '' } })
  },
)

const submit = handleSubmit((values) => {
  const parsed = z
    .object({
      password: z.string().min(10, '密码至少需要 10 个字符').max(256),
      confirmation: z.string(),
    })
    .refine((value) => value.password === value.confirmation, {
      path: ['confirmation'],
      message: '两次输入的密码不一致',
    })
    .safeParse(values)
  if (!parsed.success) {
    const fieldErrors = parsed.error.flatten().fieldErrors
    setErrors({
      password: fieldErrors.password?.[0],
      confirmation: fieldErrors.confirmation?.[0],
    })
    return
  }
  emit('save', parsed.data.password)
})
</script>

<template>
  <FormDialog
    :show="show"
    title="重置密码"
    size="sm"
    :submitting="submitting"
    @update:show="$emit('update:show', $event)"
    @submit="submit"
    @cancel="$emit('update:show', false)"
  >
    <NForm label-placement="top" @submit.prevent="submit">
      <NFormItem label="新密码" :feedback="errors.password">
        <AppInput
          v-model="password"
          type="password"
          :maxlength="256"
          autocomplete="off"
        />
      </NFormItem>
      <NFormItem label="确认新密码" :feedback="errors.confirmation">
        <AppInput
          v-model="confirmation"
          type="password"
          :maxlength="256"
          autocomplete="off"
        />
      </NFormItem>
    </NForm>
  </FormDialog>
</template>
