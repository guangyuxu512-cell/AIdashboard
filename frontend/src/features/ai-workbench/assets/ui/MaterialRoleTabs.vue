<script setup lang="ts">
import { computed } from 'vue'

import { MATERIAL_ROLE_META, type MaterialRole } from '../model/types'
import ContextSwitchBar from '@/shared/components/ContextSwitchBar.vue'

const props = defineProps<{
  modelValue: MaterialRole
  counts: Record<MaterialRole, number>
}>()

const emit = defineEmits<{
  'update:modelValue': [role: MaterialRole]
}>()

const roles: readonly MaterialRole[] = [
  'PRODUCT_SOURCE',
  'STYLE_REFERENCE',
  'AI_OUTPUT',
]

const items = computed(() =>
  roles.map((role) => ({
    key: role,
    label: `${MATERIAL_ROLE_META[role].label} ${props.counts[role]}`,
  })),
)

function updateRole(role: string): void {
  emit('update:modelValue', role as MaterialRole)
}
</script>

<template>
  <ContextSwitchBar
    class="material-role-tabs"
    label="素材角色"
    appearance="bare"
    :items="items"
    :active-key="modelValue"
    @select="updateRole"
  />
</template>

<style scoped>
.material-role-tabs {
  flex: 0 0 auto;
}
</style>
