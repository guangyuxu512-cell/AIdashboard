<script setup lang="ts">
import { computed, watch } from 'vue'
import { NCheckbox, NCheckboxGroup, NForm, NFormItem } from 'naive-ui'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import type {
  AccessDataScope,
  AccessMembershipInput,
  AccessMembershipViewModel,
  AccessRoleCode,
  AccessTeamViewModel,
} from '@/entities/access-management'
import FormDialog from '@/shared/components/FormDialog.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'
import AppSwitch from '@/shared/ui/AppSwitch.vue'

const props = defineProps<{
  show: boolean
  membership: AccessMembershipViewModel | null
  teams: AccessTeamViewModel[]
  moduleOptions: Array<{ value: string; label: string }>
  submitting?: boolean
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  save: [input: AccessMembershipInput]
}>()

interface MembershipFormValues {
  teamId: string | null
  roleCode: AccessRoleCode
  dataScope: AccessDataScope
  enabled: boolean
  moduleCodes: string[]
}

const emptyForm: MembershipFormValues = {
  teamId: null,
  roleCode: 'member',
  dataScope: 'team',
  enabled: true,
  moduleCodes: [],
}

const schema = z.object({
  teamId: z.string().min(1, '请选择团队'),
  roleCode: z.enum(['member', 'access_admin']),
  dataScope: z.enum(['self', 'team', 'all']),
  enabled: z.boolean(),
  moduleCodes: z.array(z.string()),
})

const { defineField, errors, handleSubmit, resetForm, setErrors } =
  useForm<MembershipFormValues>({ initialValues: emptyForm })
const [teamId] = defineField('teamId')
const [roleCode] = defineField('roleCode')
const [dataScope] = defineField('dataScope')
const [enabled] = defineField('enabled')
const [moduleCodes] = defineField('moduleCodes')

const teamOptions = computed(() =>
  props.teams
    .filter((team) => team.enabled || team.teamId === props.membership?.teamId)
    .map((team) => ({ value: team.teamId, label: team.name })),
)
const editing = computed(() => props.membership !== null)

watch(
  () => [props.show, props.membership] as const,
  ([show, membership]) => {
    if (!show) return
    resetForm({
      values: membership
        ? {
            teamId: membership.teamId,
            roleCode: membership.roleCode,
            dataScope: membership.dataScope,
            enabled: membership.enabled,
            moduleCodes: [...membership.moduleCodes],
          }
        : { ...emptyForm },
    })
  },
)

const submit = handleSubmit((values) => {
  const parsed = schema.safeParse(values)
  if (!parsed.success) {
    setErrors({ teamId: parsed.error.flatten().fieldErrors.teamId?.[0] })
    return
  }
  emit('save', {
    teamId: parsed.data.teamId,
    roleCode: parsed.data.roleCode,
    dataScope: parsed.data.dataScope,
    enabled: parsed.data.enabled,
    moduleCodes: parsed.data.moduleCodes,
  })
})
</script>

<template>
  <FormDialog
    :show="show"
    :title="editing ? '编辑团队关系' : '加入团队'"
    size="md"
    :submitting="submitting"
    @update:show="$emit('update:show', $event)"
    @submit="submit"
    @cancel="$emit('update:show', false)"
  >
    <NForm label-placement="top" @submit.prevent="submit">
      <div class="access-membership-form__grid">
        <NFormItem label="团队" :feedback="errors.teamId">
          <AppSelect
            v-model="teamId"
            :disabled="editing"
            :options="teamOptions"
          />
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
      <div class="access-membership-form__grid">
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
          <AppSwitch v-model="enabled" />
        </NFormItem>
      </div>
      <NFormItem label="功能权限">
        <NCheckboxGroup v-model:value="moduleCodes">
          <div class="access-membership-form__modules">
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
.access-membership-form__grid {
  display: grid;
  gap: var(--layout-card-gap);
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.access-membership-form__modules {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}

@media (max-width: 640px) {
  .access-membership-form__grid,
  .access-membership-form__modules {
    grid-template-columns: 1fr;
  }
}
</style>
