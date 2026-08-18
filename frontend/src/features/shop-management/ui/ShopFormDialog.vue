<script setup lang="ts">
import { computed, watch } from 'vue'
import { NForm, NFormItem } from 'naive-ui'
import type { SelectOption } from 'naive-ui'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import type { ShopPlatform } from '@/entities/shop'
import FormDialog from '@/shared/components/FormDialog.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'
import AppSwitch from '@/shared/ui/AppSwitch.vue'
import type { AppOptionValue } from '@/shared/ui/types'

import type { ShopFormMode, ShopFormViewModel } from '../model/types'

const props = defineProps<{
  show: boolean
  mode: ShopFormMode
  initialValue: ShopFormViewModel | null
  platformOptions: SelectOption[]
  ownerOptions: SelectOption[]
  ownerOptionsLoading?: boolean
  submitting?: boolean
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  save: [value: ShopFormViewModel]
}>()

const emptyForm: ShopFormViewModel = {
  shopName: '',
  platform: null,
  enabled: true,
  ownerUserId: null,
  note: '',
}

const formSchema = z.object({
  shopName: z
    .string()
    .trim()
    .min(1, '请输入店铺名称')
    .max(100, '店铺名称最多 100 个字符'),
  platform: z
    .enum(['douyin', 'taobao', 'pdd', 'jd'])
    .nullable()
    .refine((value) => value !== null, '请选择平台'),
  enabled: z.boolean(),
  ownerUserId: z.string().nullable(),
  note: z.string().trim().max(1000, '备注最多 1000 个字符'),
})

const { defineField, errors, handleSubmit, resetForm, setErrors } =
  useForm<ShopFormViewModel>({
    initialValues: emptyForm,
  })

const [shopName] = defineField('shopName')
const [platform] = defineField('platform')
const [enabled] = defineField('enabled')
const [ownerUserId] = defineField('ownerUserId')
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
          : {
              ...emptyForm,
              platform:
                (props.platformOptions[0]?.value as ShopPlatform | undefined) ??
                null,
            },
      })
    }
  },
)

function updatePlatform(value: AppOptionValue | null): void {
  platform.value = value as ShopPlatform | null
}

function updateOwner(value: AppOptionValue | null): void {
  ownerUserId.value = value as string | null
}

const submit = handleSubmit((values) => {
  const parsed = formSchema.safeParse(values)
  if (!parsed.success) {
    const fieldErrors = parsed.error.flatten().fieldErrors
    setErrors({
      shopName: fieldErrors.shopName?.[0],
      platform: fieldErrors.platform?.[0],
      enabled: fieldErrors.enabled?.[0],
      ownerUserId: fieldErrors.ownerUserId?.[0],
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
      <div class="shop-form__grid">
        <NFormItem
          label="店铺名称"
          :validation-status="errors.shopName ? 'error' : undefined"
          :feedback="errors.shopName"
        >
          <AppInput
            v-model="shopName"
            :maxlength="100"
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
            :options="platformOptions"
            placeholder="请选择平台"
            @update:model-value="updatePlatform"
          />
        </NFormItem>
        <NFormItem
          label="负责人"
          :validation-status="errors.ownerUserId ? 'error' : undefined"
          :feedback="errors.ownerUserId"
        >
          <AppSelect
            :model-value="ownerUserId"
            :options="ownerOptions"
            :loading="ownerOptionsLoading"
            clearable
            placeholder="可选负责人"
            @update:model-value="updateOwner"
          />
        </NFormItem>
        <NFormItem label="启用状态">
          <AppSwitch v-model="enabled" />
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
          :maxlength="1000"
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
