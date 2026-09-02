<script setup lang="ts">
import { computed, watch } from 'vue'
import { NCheckbox, NCheckboxGroup, NForm, NFormItem } from 'naive-ui'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import type {
  AccessDataScope,
  AccessMemberCreateInput,
  AccessRoleCode,
  AccessTeamViewModel,
} from '@/entities/access-management'
import FormDialog from '@/shared/components/FormDialog.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'
import AppSwitch from '@/shared/ui/AppSwitch.vue'

const props = defineProps<{
  show: boolean
  teams: AccessTeamViewModel[]
  moduleOptions: Array<{ value: string; label: string }>
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
  roleCode: AccessRoleCode
  dataScope: AccessDataScope
  membershipEnabled: boolean
  moduleCodes: string[]
}

const emptyForm: MemberFormValues = {
  displayName: '',
  loginName: '',
  password: '',
  teamId: null,
  roleCode: 'member',
  dataScope: 'team',
  membershipEnabled: true,
  moduleCodes: [],
}

const schema = z.object({
  displayName: z.string().trim().min(1, '请输入显示名').max(100),
  loginName: z.string().trim().min(1, '请输入登录账号').max(100),
  password: z.string().min(10, '密码至少需要 10 个字符').max(256),
  teamId: z.string().min(1, '请选择团队'),
  roleCode: z.enum(['member', 'access_admin']),
  dataScope: z.enum(['self', 'team', 'all']),
  membershipEnabled: z.boolean(),
  moduleCodes: z.array(z.string()),
})

const { defineField, errors, handleSubmit, resetForm, setErrors } =
  useForm<MemberFormValues>({ initialValues: emptyForm })
const [displayName] = defineField('displayName')
const [loginName] = defineField('loginName')
const [password] = defineField('password')
const [teamId] = defineField('teamId')
const [roleCode] = defineField('roleCode')
const [dataScope] = defineField('dataScope')
const [membershipEnabled] = defineField('membershipEnabled')
const [moduleCodes] = defineField('moduleCodes')

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
    membership: {
      teamId: parsed.data.teamId,
      roleCode: parsed.data.roleCode,
      dataScope: parsed.data.dataScope,
      enabled: parsed.data.membershipEnabled,
      moduleCodes: parsed.data.moduleCodes,
    },
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
      <div class="access-member-form__grid">
        <NFormItem label="团队" :feedback="errors.teamId">
          <AppSelect v-model="teamId" :options="teamOptions" />
        </NFormItem>
        <NFormItem label="角色">
          <AppSelect
            v-model="roleCode"
            :options="[
              { value: 'member', label: '成员' },
              { value: 'access_admin', label: '权限管理员' },
            ]"
          />
        </NFormItem>
      </div>
      <div class="access-member-form__grid">
        <NFormItem label="数据范围">
          <AppSelect
            v-model="dataScope"
            :options="[
              { value: 'self', label: 'SELF' },
              { value: 'team', label: 'TEAM' },
              { value: 'all', label: 'ALL' },
            ]"
          />
        </NFormItem>
        <NFormItem label="成员关系启用">
          <AppSwitch v-model="membershipEnabled" />
        </NFormItem>
      </div>
      <NFormItem label="功能权限">
        <NCheckboxGroup v-model:value="moduleCodes">
          <div class="access-member-form__modules">
            <NCheckbox
              v-for="module in moduleOptions"
              :key="module.value"
              :value="module.value"
            >
              {{ module.label }}
            </NCheckbox>
          </div>
        </NCheckboxGroup>
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

.access-member-form__modules {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}

@media (max-width: 640px) {
  .access-member-form__grid,
  .access-member-form__modules {
    grid-template-columns: 1fr;
  }
}
</style>
