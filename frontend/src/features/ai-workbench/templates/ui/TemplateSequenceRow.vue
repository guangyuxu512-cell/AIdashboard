<script setup lang="ts">
import { computed } from 'vue'
import { MoreHorizontal } from '@lucide/vue'
import { NDropdown } from 'naive-ui'
import type { DropdownOption } from 'naive-ui'

import { TEMPLATE_OUTPUT_ROLE_META, type PromptTemplate } from '../model/types'
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
  <article
    class="template-sequence-row"
    :class="{ 'template-sequence-row--active': active }"
    :data-template-id="template.id"
    :data-output-role="template.outputRole"
    :data-sort-order="template.sortOrder"
    @click="$emit('select')"
  >
    <button
      class="template-sequence-row__select"
      type="button"
      :aria-label="`选择模板 ${template.name}`"
      :aria-pressed="active"
    >
      <span class="template-sequence-row__order">{{ template.sortOrder }}</span>
      <strong class="template-sequence-row__name" :title="template.name">
        {{ template.name }}
      </strong>
      <span class="template-sequence-row__role">
        {{ TEMPLATE_OUTPUT_ROLE_META[template.outputRole].label }}
      </span>
      <span class="template-sequence-row__size">{{ template.size }}</span>
      <span
        class="template-sequence-row__status"
        :class="{ 'template-sequence-row__status--enabled': template.enabled }"
        :aria-label="template.enabled ? '启用' : '停用'"
        role="status"
      />
    </button>
    <div class="template-sequence-row__actions" @click.stop>
      <NDropdown trigger="click" :options="menuOptions" @select="selectAction">
        <AppButton tone="text" :aria-label="`${template.name}操作`">
          <MoreHorizontal :size="16" />
        </AppButton>
      </NDropdown>
    </div>
  </article>
</template>

<style scoped>
.template-sequence-row {
  display: grid;
  width: 100%;
  height: var(--table-list-row-slot-height);
  min-width: 0;
  grid-template-columns: minmax(0, 1fr) var(--control-height-default);
  align-items: center;
  gap: var(--space-1);
  padding: 0 var(--space-1) 0 var(--space-2);
  overflow: hidden;
  border: 1px solid transparent;
  border-radius: var(--radius-control);
  cursor: pointer;
}

.template-sequence-row + .template-sequence-row {
  margin-top: var(--space-1);
}

.template-sequence-row:hover {
  background: var(--bg-surface-hover);
}

.template-sequence-row--active {
  border-color: var(--border-default);
  background: var(--color-primary-soft);
}

.template-sequence-row__select {
  display: grid;
  width: 100%;
  height: 100%;
  min-width: 0;
  grid-template-columns:
    var(--control-height-compact)
    minmax(0, 1fr)
    var(--control-height-default)
    var(--control-height-large)
    var(--space-3);
  align-items: center;
  gap: var(--space-2);
  padding: 0;
  border: 0;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: inherit;
  background: transparent;
}

.template-sequence-row__order {
  color: var(--text-tertiary);
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.template-sequence-row__name {
  min-width: 0;
  overflow: hidden;
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
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
  text-align: right;
}

.template-sequence-row__status {
  display: block;
  width: var(--space-2);
  height: var(--space-2);
  justify-self: center;
  border: 1px solid var(--border-strong);
  border-radius: 50%;
  background: transparent;
}

.template-sequence-row__status--enabled {
  border-color: var(--status-success);
  background: var(--status-success);
}

.template-sequence-row__actions {
  display: grid;
  height: 100%;
  place-items: center;
}
</style>
