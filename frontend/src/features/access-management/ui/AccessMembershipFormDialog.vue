<script setup lang="ts">
import { computed, watch } from 'vue'
import { NAlert, NForm, NFormItem } from 'naive-ui'
import { useForm } from 'vee-validate'
import { z } from 'zod'

import type {
  AccessMemberTeamInput,
  AccessMemberViewModel,
  AccessTeamViewModel,
} from '@/entities/access-management'
import FormDialog from '@/shared/components/FormDialog.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'

const props = defineProps<{
  show: boolean
  member: AccessMemberViewModel | null
  teams: AccessTeamViewModel[]
  submitting?: boolean
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  save: [input: AccessMemberTeamInput]
}>()

const currentMembership = computed(() =>
  props.member?.memberships.find(
    (membership) => membership.enabled && membership.teamEnabled,
  ),
)
const teamOptions = computed(() =>
  props.teams
    .filter((team) => team.enabled)
    .map((team) => ({ value: team.teamId, label: team.name })),
)

const { defineField, errors, handleSubmit, resetForm, setErrors } = useForm<{
  teamId: string | null
}>({ initialValues: { teamId: null } })
const [teamId] = defineField('teamId')

watch(
  () => [props.show, props.member] as const,
  ([show]) => {
    if (show) {
      resetForm({ values: { teamId: currentMembership.value?.teamId ?? null } })
    }
  },
)

const submit = handleSubmit((values) => {
  const parsed = z.object({ teamId: z.string().uuid().nullable() }).safeParse(values)
  if (!parsed.success) {
    setErrors({ teamId: parsed.error.flatten().fieldErrors.teamId?.[0] })
    return
  }
  emit('save', { teamId: parsed.data.teamId })
})
</script>

<template>
  <FormDialog
    :show="show"
    title="调整成员团队"
    size="sm"
    :submitting="submitting"
    @update:show="$emit('update:show', $event)"
    @submit="submit"
    @cancel="$emit('update:show', false)"
  >
    <NForm label-placement="top" @submit.prevent="submit">
      <NAlert type="info" :bordered="false" class="access-membership-form__hint">
        调组后立即撤销旧团队权限，并由新团队的模块、设备和店铺授权决定后续访问范围。历史业务数据不会随成员转移。
      </NAlert>
      <NFormItem label="目标团队（可选）" :feedback="errors.teamId">
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
.access-membership-form__hint {
  margin-bottom: var(--space-4);
}
</style>
