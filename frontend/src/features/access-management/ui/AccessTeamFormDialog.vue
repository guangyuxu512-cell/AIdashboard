<script setup lang="ts">
import { computed, watch } from 'vue'
import { NForm, NFormItem } from 'naive-ui'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import type {
  AccessTeamInput,
  AccessTeamViewModel,
} from '@/entities/access-management'
import FormDialog from '@/shared/components/FormDialog.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import AppSwitch from '@/shared/ui/AppSwitch.vue'

const props = defineProps<{
  show: boolean
  team: AccessTeamViewModel | null
  submitting?: boolean
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  save: [input: AccessTeamInput]
}>()

const { defineField, errors, handleSubmit, resetForm, setErrors } =
  useForm<AccessTeamInput>({ initialValues: { name: '', enabled: true } })
const [name] = defineField('name')
const [enabled] = defineField('enabled')
const editing = computed(() => props.team !== null)

watch(
  () => [props.show, props.team] as const,
  ([show, team]) => {
    if (show)
      resetForm({
        values: team
          ? { name: team.name, enabled: team.enabled }
          : { name: '', enabled: true },
      })
  },
)

const submit = handleSubmit((values) => {
  const parsed = z
    .object({
      name: z.string().trim().min(1, '请输入团队名称').max(100),
      enabled: z.boolean(),
    })
    .safeParse(values)
  if (!parsed.success) {
    setErrors({ name: parsed.error.flatten().fieldErrors.name?.[0] })
    return
  }
  emit('save', parsed.data)
})
</script>

<template>
  <FormDialog
    :show="show"
    :title="editing ? '编辑团队' : '新增团队'"
    size="sm"
    :submitting="submitting"
    @update:show="$emit('update:show', $event)"
    @submit="submit"
    @cancel="$emit('update:show', false)"
  >
    <NForm label-placement="top" @submit.prevent="submit">
      <NFormItem label="团队名称" :feedback="errors.name">
        <AppInput v-model="name" :maxlength="100" />
      </NFormItem>
      <NFormItem label="启用团队">
        <AppSwitch v-model="enabled" />
      </NFormItem>
    </NForm>
  </FormDialog>
</template>
