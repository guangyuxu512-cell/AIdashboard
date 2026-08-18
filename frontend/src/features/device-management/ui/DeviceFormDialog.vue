<script setup lang="ts">
import { computed, watch } from 'vue'
import { NForm, NFormItem } from 'naive-ui'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import FormDialog from '@/shared/components/FormDialog.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import AppSwitch from '@/shared/ui/AppSwitch.vue'

import type { DeviceFormMode, DeviceFormViewModel } from '../model/types'

const props = defineProps<{
  show: boolean
  mode: DeviceFormMode
  initialValue: DeviceFormViewModel | null
  submitting?: boolean
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  save: [value: DeviceFormViewModel]
}>()

const emptyForm: DeviceFormViewModel = {
  deviceName: '',
  enabled: true,
  location: '',
  note: '',
}

const formSchema = z.object({
  deviceName: z.string().trim().min(1, '请输入设备名称').max(100),
  enabled: z.boolean(),
  location: z.string().trim().max(200, '位置最多 200 个字符'),
  note: z.string().trim().max(1000, '备注最多 1000 个字符'),
})

const { defineField, errors, handleSubmit, resetForm, setErrors } =
  useForm<DeviceFormViewModel>({ initialValues: emptyForm })

const [deviceName] = defineField('deviceName')
const [enabled] = defineField('enabled')
const [location] = defineField('location')
const [note] = defineField('note')
const title = computed(() =>
  props.mode === 'create' ? '创建设备基础记录' : '编辑设备基础记录',
)

watch(
  () => [props.show, props.initialValue] as const,
  ([show]) => {
    if (show) {
      resetForm({
        values: props.initialValue
          ? { ...props.initialValue }
          : { ...emptyForm },
      })
    }
  },
)

const submit = handleSubmit((values) => {
  const parsed = formSchema.safeParse(values)
  if (!parsed.success) {
    const fieldErrors = parsed.error.flatten().fieldErrors
    setErrors({
      deviceName: fieldErrors.deviceName?.[0],
      enabled: fieldErrors.enabled?.[0],
      location: fieldErrors.location?.[0],
      note: fieldErrors.note?.[0],
    })
    return
  }
  emit('save', parsed.data)
})
</script>

<template>
  <FormDialog
    :show="show"
    :title="title"
    size="md"
    :submitting="submitting"
    @update:show="$emit('update:show', $event)"
    @submit="submit"
    @cancel="$emit('update:show', false)"
  >
    <NForm label-placement="top" @submit.prevent="submit">
      <NFormItem
        label="设备名称"
        :validation-status="errors.deviceName ? 'error' : undefined"
        :feedback="errors.deviceName"
      >
        <AppInput
          v-model="deviceName"
          :maxlength="100"
          placeholder="请输入设备名称"
        />
      </NFormItem>
      <NFormItem label="启用状态">
        <AppSwitch v-model="enabled" />
      </NFormItem>
      <NFormItem
        label="位置"
        :validation-status="errors.location ? 'error' : undefined"
        :feedback="errors.location"
      >
        <AppInput
          v-model="location"
          :maxlength="200"
          placeholder="请输入位置（选填）"
        />
      </NFormItem>
      <NFormItem
        label="备注"
        :validation-status="errors.note ? 'error' : undefined"
        :feedback="errors.note"
      >
        <AppInput
          v-model="note"
          type="textarea"
          :maxlength="1000"
          placeholder="请输入备注（选填）"
        />
      </NFormItem>
      <p class="device-form__hint">
        创建设备记录不代表 Worker 已注册，也不代表设备在线。
      </p>
    </NForm>
  </FormDialog>
</template>

<style scoped>
.device-form__hint {
  color: var(--color-text-secondary);
  font-size: var(--font-size-secondary);
}
</style>
