<script setup lang="ts">
import { computed } from 'vue'
import { Plus } from '@lucide/vue'
import { NDropdown } from 'naive-ui'
import type { DropdownOption } from 'naive-ui'

import {
  TEMPLATE_OUTPUT_ROLE_META,
  type PromptTemplate,
  type TemplateGroup,
  type TemplateOutputRole,
  type TemplateRoleFilter,
} from '../model/types'
import TemplateSequenceRow from './TemplateSequenceRow.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'
import { AppButton } from '@/shared/ui'

const props = defineProps<{
  group: TemplateGroup | null
  templates: readonly PromptTemplate[]
  roleFilter: TemplateRoleFilter
  selectedTemplateId: string | null
  page: number
  pageSize: number
  itemCount: number
}>()

const emit = defineEmits<{
  create: [outputRole: TemplateOutputRole]
  filter: [roleFilter: TemplateRoleFilter]
  select: [templateId: string]
  move: [templateId: string, direction: 'up' | 'down']
  duplicate: [templateId: string]
  remove: [template: PromptTemplate]
  'update:page': [value: number]
  'update:pageSize': [value: number]
}>()

const createOptions: DropdownOption[] = [
  { key: 'MAIN_IMAGE', label: TEMPLATE_OUTPUT_ROLE_META.MAIN_IMAGE.label },
  { key: 'DETAIL_IMAGE', label: TEMPLATE_OUTPUT_ROLE_META.DETAIL_IMAGE.label },
]

const roleCounts = computed(() => {
  const templates = props.group?.templates ?? []
  return {
    main: templates.filter((template) => template.outputRole === 'MAIN_IMAGE')
      .length,
    detail: templates.filter(
      (template) => template.outputRole === 'DETAIL_IMAGE',
    ).length,
  }
})

const roleFilterItems = computed<
  Array<{ key: TemplateRoleFilter; label: string }>
>(() => [
  {
    key: 'ALL',
    label: `全部 ${props.group?.templates.length ?? 0}`,
  },
  {
    key: 'MAIN_IMAGE',
    label: `${TEMPLATE_OUTPUT_ROLE_META.MAIN_IMAGE.label} ${roleCounts.value.main}`,
  },
  {
    key: 'DETAIL_IMAGE',
    label: `${TEMPLATE_OUTPUT_ROLE_META.DETAIL_IMAGE.label} ${roleCounts.value.detail}`,
  },
])

const templateIdsByRole = computed<Record<TemplateOutputRole, string[]>>(() => {
  const templates = [...(props.group?.templates ?? [])].sort(
    (left, right) => left.sortOrder - right.sortOrder,
  )
  return {
    MAIN_IMAGE: templates
      .filter((template) => template.outputRole === 'MAIN_IMAGE')
      .map((template) => template.id),
    DETAIL_IMAGE: templates
      .filter((template) => template.outputRole === 'DETAIL_IMAGE')
      .map((template) => template.id),
  }
})

function createTemplate(key: string | number): void {
  if (key === 'MAIN_IMAGE' || key === 'DETAIL_IMAGE') {
    emit('create', key)
  }
}

function canMove(template: PromptTemplate, direction: 'up' | 'down'): boolean {
  const roleIds = templateIdsByRole.value[template.outputRole]
  const index = roleIds.indexOf(template.id)
  return direction === 'up'
    ? index > 0
    : index >= 0 && index < roleIds.length - 1
}
</script>

<template>
  <section class="template-sequence-list" aria-label="模板序列">
    <template v-if="group">
      <header class="template-sequence-list__header">
        <div class="template-sequence-list__title">
          <strong :title="group.name">{{ group.name }}</strong>
        </div>
        <div class="template-sequence-list__actions">
          <div
            class="template-role-filter"
            role="group"
            aria-label="模板角色筛选"
          >
            <AppButton
              v-for="item in roleFilterItems"
              :key="item.key"
              class="template-role-filter__button"
              :tone="roleFilter === item.key ? 'secondary' : 'text'"
              :aria-pressed="roleFilter === item.key"
              :data-role-filter="item.key"
              @click="$emit('filter', item.key)"
            >
              {{ item.label }}
            </AppButton>
          </div>
          <NDropdown
            trigger="click"
            :options="createOptions"
            @select="createTemplate"
          >
            <AppButton
              class="template-sequence-list__add"
              tone="text"
              aria-label="添加模板"
            >
              <Plus :size="16" />
              添加
            </AppButton>
          </NDropdown>
        </div>
      </header>

      <div class="template-sequence-list__scroll">
        <EmptyState v-if="templates.length === 0" description="暂无模板" />
        <template v-else>
          <TemplateSequenceRow
            v-for="template in templates"
            :key="template.id"
            :template="template"
            :active="template.id === selectedTemplateId"
            :can-move-up="canMove(template, 'up')"
            :can-move-down="canMove(template, 'down')"
            @select="$emit('select', template.id)"
            @move="$emit('move', template.id, $event)"
            @duplicate="$emit('duplicate', template.id)"
            @remove="$emit('remove', template)"
          />
        </template>
      </div>

      <PaginationBar
        class="template-sequence-list__pagination"
        :page="page"
        :page-size="pageSize"
        :item-count="itemCount"
        @update:page="$emit('update:page', $event)"
        @update:page-size="$emit('update:pageSize', $event)"
      />
    </template>
    <EmptyState v-else description="暂无模板组" />
  </section>
</template>

<style scoped>
.template-sequence-list {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  overflow: hidden;
  padding: var(--space-4);
}

.template-sequence-list__header {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
}

.template-sequence-list__title {
  display: flex;
  min-width: 0;
  flex: 1 1 auto;
  align-items: baseline;
  gap: var(--space-2);
}

.template-sequence-list__title > strong {
  min-width: 0;
  overflow: hidden;
  color: var(--text-primary);
  font-size: var(--font-size-section-title);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.template-sequence-list__actions,
.template-role-filter {
  display: flex;
  align-items: center;
}

.template-sequence-list__actions {
  flex: 0 0 auto;
  gap: var(--space-3);
}

.template-role-filter {
  gap: var(--space-2);
}

.template-role-filter__button,
.template-sequence-list__add {
  padding-inline: var(--space-1);
  white-space: nowrap;
}

.template-sequence-list__scroll {
  min-height: 0;
  flex: 1;
  padding: var(--space-3) 0;
  overflow-y: auto;
  scrollbar-width: none;
}

.template-sequence-list__scroll::-webkit-scrollbar {
  display: none;
}

.template-sequence-list__pagination {
  flex: 0 0 auto;
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}
</style>
