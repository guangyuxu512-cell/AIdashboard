<script setup lang="ts">
import { Folder, MoreHorizontal, Plus } from '@lucide/vue'
import { NDropdown } from 'naive-ui'
import type { DropdownOption } from 'naive-ui'

import type { TemplateGroup } from '../model/types'
import CompactEntityRow from '@/shared/components/CompactEntityRow.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { AppButton } from '@/shared/ui'

defineProps<{
  groups: readonly TemplateGroup[]
  selectedGroupId: string | null
}>()

const emit = defineEmits<{
  create: []
  select: [groupId: string]
  rename: [group: TemplateGroup]
  remove: [group: TemplateGroup]
}>()

const menuOptions: DropdownOption[] = [
  { key: 'rename', label: '重命名' },
  { key: 'remove', label: '删除' },
]

function selectAction(group: TemplateGroup, key: string | number): void {
  if (key === 'rename') emit('rename', group)
  if (key === 'remove') emit('remove', group)
}
</script>

<template>
  <section class="template-group-sidebar" aria-label="模板组列表">
    <div class="template-group-sidebar__header">
      <strong>模板组</strong>
      <AppButton tone="text" aria-label="新建模板组" @click="$emit('create')">
        <Plus :size="16" />
        新建
      </AppButton>
    </div>

    <div class="template-group-sidebar__list">
      <EmptyState v-if="groups.length === 0" description="暂无模板组" />
      <CompactEntityRow
        v-for="group in groups"
        v-else
        :key="group.id"
        class="template-group-sidebar__item"
        :title="group.name"
        :count="group.templates.length"
        :active="group.id === selectedGroupId"
        :select-label="`选择模板组 ${group.name}`"
        :data-template-group-id="group.id"
        @select="$emit('select', group.id)"
      >
        <template #icon>
          <Folder :size="18" />
        </template>
        <template #status>
          <span
            class="template-group-sidebar__status"
            :class="{
              'template-group-sidebar__status--enabled': group.enabled,
            }"
            :aria-label="group.enabled ? '启用' : '停用'"
            role="status"
          />
        </template>
        <template #actions>
          <NDropdown
            trigger="click"
            :options="menuOptions"
            @select="selectAction(group, $event)"
          >
            <AppButton tone="text" :aria-label="`${group.name}操作`">
              <MoreHorizontal :size="16" />
            </AppButton>
          </NDropdown>
        </template>
      </CompactEntityRow>
    </div>
  </section>
</template>

<style scoped>
.template-group-sidebar {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}

.template-group-sidebar__header {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
}

.template-group-sidebar__header > strong {
  color: var(--text-primary);
  font-size: var(--font-size-section-title);
}

.template-group-sidebar__list {
  min-height: 0;
  flex: 1;
  padding: var(--space-2);
  overflow-y: auto;
  scrollbar-width: none;
}

.template-group-sidebar__list::-webkit-scrollbar {
  display: none;
}

.template-group-sidebar__status {
  display: block;
  width: var(--space-2);
  height: var(--space-2);
  border: 1px solid var(--border-strong);
  border-radius: 50%;
  background: transparent;
}

.template-group-sidebar__status--enabled {
  border-color: var(--status-success);
  background: var(--status-success);
}
</style>
