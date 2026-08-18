<script setup lang="ts">
import { computed, watch } from 'vue'
import { NForm, NFormItem } from 'naive-ui'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import {
  SHOP_DEVICE_FIXTURE_OPTIONS,
  SHOP_PLATFORM_FIXTURE_OPTIONS,
  type ShopPlatform,
} from '@/entities/shop'
import FormDialog from '@/shared/components/FormDialog.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'
import type { AppOptionValue } from '@/shared/ui/types'

import type { ShopFormMode, ShopFormViewModel } from '../model/types'

const props = defineProps<{
  show: boolean
  mode: ShopFormMode
  initialValue: ShopFormViewModel | null
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  save: [value: ShopFormViewModel]
}>()

const emptyForm: ShopFormViewModel = {
  shopName: '',
  platform: null,
  ownerName: '',
  executionDeviceId: null,
  note: '',
}

const formSchema = z.object({
  shopName: z
    .string()
    .trim()
    .min(1, '请输入店铺名称')
    .max(50, '店铺名称最多 50 个字符'),
  platform: z
    .enum(['douyin', 'taobao', 'pdd', 'jd'])
    .nullable()
    .refine((value) => value !== null, '请选择平台'),
  ownerName: z
    .string()
    .trim()
    .min(1, '请输入负责人')
    .max(20, '负责人最多 20 个字符'),
  executionDeviceId: z.string().nullable(),
  note: z.string().trim().max(200, '备注最多 200 个字符'),
})

const { defineField, errors, handleSubmit, resetForm, setErrors } =
  useForm<ShopFormViewModel>({
    initialValues: emptyForm,
  })

const [shopName] = defineField('shopName')
const [platform] = defineField('platform')
const [ownerName] = defineField('ownerName')
const [executionDeviceId] = defineField('executionDeviceId')
const [note] = defineField('note')

const title = computed(() =>
  props.mode === 'create' ? '新增店铺' : '编辑店铺',
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

function updatePlatform(value: AppOptionValue | null): void {
  platform.value = value as ShopPlatform | null
}

function updateDevice(value: AppOptionValue | null): void {
  executionDeviceId.value = value as string | null
}

const submit = handleSubmit((values) => {
  const parsed = formSchema.safeParse(values)
  if (!parsed.success) {
    const fieldErrors = parsed.error.flatten().fieldErrors
    setErrors({
      shopName: fieldErrors.shopName?.[0],
      platform: fieldErrors.platform?.[0],
      ownerName: fieldErrors.ownerName?.[0],
      executionDeviceId: fieldErrors.executionDeviceId?.[0],
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
    @update:show="$emit('update:show', $event)"
    @submit="submit"
    @cancel="$emit('update:show', false)"
  >
    <NForm label-placement="top" @submit.prevent="submit">
      <div class="shop-form__grid">
        <NFormItem
          label="店铺名称"
          :validation-status="errors.shopName ? 'error' : undefined"
          :feedback="errors.shopName"
        >
          <AppInput
            v-model="shopName"
            :maxlength="50"
            placeholder="请输入店铺名称"
          />
        </NFormItem>
        <NFormItem
          label="平台"
          :validation-status="errors.platform ? 'error' : undefined"
          :feedback="errors.platform"
        >
          <AppSelect
            :model-value="platform"
            :options="SHOP_PLATFORM_FIXTURE_OPTIONS"
            placeholder="请选择平台"
            @update:model-value="updatePlatform"
          />
        </NFormItem>
        <NFormItem
          label="负责人"
          :validation-status="errors.ownerName ? 'error' : undefined"
          :feedback="errors.ownerName"
        >
          <AppInput
            v-model="ownerName"
            :maxlength="20"
            placeholder="请输入负责人"
          />
        </NFormItem>
        <NFormItem
          label="执行设备"
          :validation-status="errors.executionDeviceId ? 'error' : undefined"
          :feedback="errors.executionDeviceId"
        >
          <AppSelect
            :model-value="executionDeviceId"
            clearable
            :options="SHOP_DEVICE_FIXTURE_OPTIONS"
            placeholder="可选 Mock 设备"
            @update:model-value="updateDevice"
          />
        </NFormItem>
      </div>
      <NFormItem
        label="备注"
        :validation-status="errors.note ? 'error' : undefined"
        :feedback="errors.note"
      >
        <AppInput
          v-model="note"
          type="textarea"
          :maxlength="200"
          placeholder="请输入备注（选填）"
        />
      </NFormItem>
    </NForm>
  </FormDialog>
</template>

<style scoped>
.shop-form__grid {
  display: grid;
  gap: 0 var(--space-4);
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

@media (max-width: 640px) {
  .shop-form__grid {
    grid-template-columns: 1fr;
  }
}
</style>
