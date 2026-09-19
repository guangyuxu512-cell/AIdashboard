<script setup lang="ts">
import { computed, watch } from 'vue'
import { NForm, NFormItem } from 'naive-ui'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import type {
  AccessMemberCreateInput,
  AccessTeamViewModel,
} from '@/entities/access-management'
import FormDialog from '@/shared/components/FormDialog.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'

const props = defineProps<{
  show: boolean
  teams: AccessTeamViewModel[]
  submitting?: boolean
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  save: [input: AccessMemberCreateInput]
}>()

interface MemberFormValues {
  displayName: string
  loginName: string
  password: string
  teamId: string | null
}

const emptyForm: MemberFormValues = {
  displayName: '',
  loginName: '',
  password: '',
  teamId: null,
}

const schema = z.object({
  displayName: z.string().trim().min(1, '请输入显示名').max(100),
  loginName: z.string().trim().min(1, '请输入登录账号').max(100),
  password: z.string().min(10, '密码至少需要 10 个字符').max(256),
  teamId: z.string().uuid().nullable(),
})

const { defineField, errors, handleSubmit, resetForm, setErrors } =
  useForm<MemberFormValues>({ initialValues: emptyForm })
const [displayName] = defineField('displayName')
const [loginName] = defineField('loginName')
const [password] = defineField('password')
const [teamId] = defineField('teamId')

const teamOptions = computed(() =>
  props.teams
    .filter((team) => team.enabled)
    .map((team) => ({ value: team.teamId, label: team.name })),
)

watch(
  () => props.show,
  (show) => {
    if (show) resetForm({ values: { ...emptyForm } })
  },
)

const submit = handleSubmit((values) => {
  const parsed = schema.safeParse(values)
  if (!parsed.success) {
    const fieldErrors = parsed.error.flatten().fieldErrors
    setErrors({
      displayName: fieldErrors.displayName?.[0],
      loginName: fieldErrors.loginName?.[0],
      password: fieldErrors.password?.[0],
      teamId: fieldErrors.teamId?.[0],
    })
    return
  }
  emit('save', {
    displayName: parsed.data.displayName,
    loginName: parsed.data.loginName,
    password: parsed.data.password,
    teamId: parsed.data.teamId,
  })
})
</script>

<template>
  <FormDialog
    :show="show"
    title="新增成员"
    size="md"
    :submitting="submitting"
    @update:show="$emit('update:show', $event)"
    @submit="submit"
    @cancel="$emit('update:show', false)"
  >
    <template #description>
      成员加入团队后继承团队已配置的模块、设备和店铺权限；也可以先创建未分配团队的成员。
    </template>
    <NForm label-placement="top" @submit.prevent="submit">
      <div class="access-member-form__grid">
        <NFormItem label="显示名" :feedback="errors.displayName">
          <AppInput v-model="displayName" :maxlength="100" />
        </NFormItem>
        <NFormItem label="登录账号" :feedback="errors.loginName">
          <AppInput
            v-model="loginName"
            :maxlength="100"
            autocomplete="username"
          />
        </NFormItem>
      </div>
      <NFormItem label="初始密码" :feedback="errors.password">
        <AppInput
          v-model="password"
          type="password"
          :maxlength="256"
          autocomplete="off"
        />
      </NFormItem>
      <NFormItem label="所属团队（可选）" :feedback="errors.teamId">
        <AppSelect
          v-model="teamId"
          clearable
          placeholder="未分配团队"
          :options="teamOptions"
        />
      </NFormItem>
    </NForm>
  </FormDialog>
</template>

<style scoped>
.access-member-form__grid {
  display: grid;
  gap: var(--layout-card-gap);
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

@media (max-width: 640px) {
  .access-member-form__grid {
    grid-template-columns: 1fr;
  }
}
</style>
