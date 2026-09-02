<script setup lang="ts">
import { computed } from 'vue'
import { MoreHorizontal } from '@lucide/vue'
import { NDropdown } from 'naive-ui'
import type { DropdownOption } from 'naive-ui'

import { TEMPLATE_OUTPUT_ROLE_META, type PromptTemplate } from '../model/types'
import CompactEntityRow from '@/shared/components/CompactEntityRow.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import { AppButton } from '@/shared/ui'

const props = defineProps<{
  template: PromptTemplate
  active: boolean
  canMoveUp: boolean
  canMoveDown: boolean
}>()

const emit = defineEmits<{
  select: []
  move: [direction: 'up' | 'down']
  duplicate: []
  remove: []
}>()

const menuOptions = computed<DropdownOption[]>(() => [
  { key: 'up', label: '上移', disabled: !props.canMoveUp },
  { key: 'down', label: '下移', disabled: !props.canMoveDown },
  { key: 'duplicate', label: '复制模板' },
  { key: 'remove', label: '删除' },
])

function selectAction(key: string | number): void {
  if (key === 'up' || key === 'down') emit('move', key)
  if (key === 'duplicate') emit('duplicate')
  if (key === 'remove') emit('remove')
}
</script>

<template>
  <CompactEntityRow
    class="template-sequence-row"
    :title="template.name"
    :count="TEMPLATE_OUTPUT_ROLE_META[template.outputRole].label"
    :active="active"
    :select-label="`选择模板 ${template.name}`"
    :data-template-id="template.id"
    :data-output-role="template.outputRole"
    :data-sort-order="template.sortOrder"
    @select="$emit('select')"
  >
    <template #icon>
      <span class="template-sequence-row__order">{{ template.sortOrder }}</span>
    </template>
    <template #title>
      <span class="template-sequence-row__title-content">
        <span class="template-sequence-row__name" :title="template.name">
          {{ template.name }}
        </span>
        <small class="template-sequence-row__size">{{ template.size }}</small>
      </span>
    </template>
    <template #count>
      <span class="template-sequence-row__role">
        {{ TEMPLATE_OUTPUT_ROLE_META[template.outputRole].label }}
      </span>
    </template>
    <template #status>
      <StatusTag
        appearance="dot"
        :label="template.enabled ? '启用' : '停用'"
        :tone="template.enabled ? 'success' : 'neutral'"
      />
    </template>
    <template #actions>
      <NDropdown trigger="click" :options="menuOptions" @select="selectAction">
        <AppButton tone="text" :aria-label="`${template.name}操作`">
          <MoreHorizontal :size="16" />
        </AppButton>
      </NDropdown>
    </template>
  </CompactEntityRow>
</template>

<style scoped>
.template-sequence-row__title-content {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--space-2);
}

.template-sequence-row__order {
  color: var(--text-tertiary);
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.template-sequence-row__name {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.template-sequence-row__role,
.template-sequence-row__size {
  font-size: var(--font-size-secondary);
}

.template-sequence-row__role {
  color: var(--text-tertiary);
  text-align: center;
}

.template-sequence-row__size {
  color: var(--text-secondary);
  font-weight: var(--font-weight-regular);
  white-space: nowrap;
}
</style>
