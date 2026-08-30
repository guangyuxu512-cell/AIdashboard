<script setup lang="ts">
import { computed, watch } from 'vue'
import { NForm, NFormItem } from 'naive-ui'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import type {
  ProductMaterialGroup,
  ProductMaterialGroupInput,
} from '../model/types'
import { AppDialog, AppInput } from '@/shared/ui'

const props = defineProps<{
  show: boolean
  mode: 'create' | 'rename'
  product: ProductMaterialGroup | null
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  save: [input: ProductMaterialGroupInput]
}>()

const schema = z.object({
  name: z
    .string()
    .trim()
    .min(1, '请输入产品名称')
    .max(100, '产品名称最多 100 个字符'),
})

const { defineField, errors, handleSubmit, resetForm, setErrors } =
  useForm<ProductMaterialGroupInput>({ initialValues: { name: '' } })
const [name] = defineField('name')
const title = computed(() =>
  props.mode === 'create' ? '新建产品' : '重命名产品',
)

watch(
  () => [props.show, props.product, props.mode] as const,
  ([show]) => {
    if (!show) return
    resetForm({
      values: {
        name: props.product?.name ?? '',
      },
    })
  },
)

const submit = handleSubmit((values) => {
  const parsed = schema.safeParse(values)
  if (!parsed.success) {
    const fieldErrors = parsed.error.flatten().fieldErrors
    setErrors({
      name: fieldErrors.name?.[0],
    })
    return
  }
  emit('save', parsed.data)
})
</script>

<template>
  <AppDialog
    :show="show"
    :title="title"
    size="sm"
    :positive-text="mode === 'create' ? '创建' : '保存'"
    @update:show="$emit('update:show', $event)"
    @confirm="submit"
  >
    <NForm label-placement="top" @submit.prevent="submit">
      <NFormItem
        label="产品名称"
        :validation-status="errors.name ? 'error' : undefined"
        :feedback="errors.name"
      >
        <AppInput
          v-model="name"
          placeholder="请输入产品名称"
          :maxlength="100"
        />
      </NFormItem>
    </NForm>
  </AppDialog>
</template>
