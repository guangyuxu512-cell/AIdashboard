<script setup lang="ts">
import { computed, ref } from 'vue'
import { Plus } from '@lucide/vue'
import type { SelectOption } from 'naive-ui'
import { useMessage } from 'naive-ui'

import { createTemplateGroupFixtures } from '../__fixtures__/template-groups.fixture'
import {
  GENERATION_MODE_META,
  type GenerationMode,
  type PromptTemplate,
  type PromptTemplateInput,
  type TemplateGroup,
  type TemplateGroupInput,
} from '../model/types'
import { useAiTemplatesVisualMock } from '../model/useAiTemplatesVisualMock'
import TemplateEditor from './TemplateEditor.vue'
import TemplateGroupFormDialog from './TemplateGroupFormDialog.vue'
import TemplateGroupSettings from './TemplateGroupSettings.vue'
import TemplateGroupSidebar from './TemplateGroupSidebar.vue'
import TemplateSequenceList from './TemplateSequenceList.vue'
import {
  AiManagementLayout,
  AiManagementToolbar,
} from '@/features/ai-workbench'
import EmptyState from '@/shared/components/EmptyState.vue'
import ThreePaneWorkbench from '@/shared/components/ThreePaneWorkbench.vue'
import { useAutoSearch } from '@/shared/composables/useAutoSearch'
import { AppButton, AppDialog, AppInput, AppSelect } from '@/shared/ui'
import type { AppOptionValue } from '@/shared/ui/types'

type PendingDelete =
  | { type: 'group'; group: TemplateGroup }
  | { type: 'template'; template: PromptTemplate }

const message = useMessage()
const groupDialogShow = ref(false)
const groupDialogMode = ref<'create' | 'rename'>('create')
const editingGroup = ref<TemplateGroup | null>(null)
const pendingDelete = ref<PendingDelete | null>(null)

const library = useAiTemplatesVisualMock(createTemplateGroupFixtures())
const {
  activeMode,
  searchQuery,
  roleFilter,
  visibleGroups,
  selectedGroupId,
  selectedGroup,
  selectedTemplateId,
  selectedTemplate,
  visibleTemplates,
  totalTemplates,
  currentPage,
  pageSize,
} = library
const searchDraft = ref(searchQuery.value)
const autoSearch = useAutoSearch(() => {
  searchQuery.value = searchDraft.value
})

const modeOptions: SelectOption[] = Object.entries(GENERATION_MODE_META).map(
  ([value, meta]) => ({ value, label: meta.label }),
)

const deleteDialogTitle = computed(() =>
  pendingDelete.value?.type === 'group' ? '删除模板组' : '删除模板',
)

const deleteDialogText = computed(() => {
  const target = pendingDelete.value
  if (!target) return ''
  if (target.type === 'group') {
    return `确认删除模板组“${target.group.name}”？`
  }
  return `确认删除模板“${target.template.name}”？`
})

function updateMode(value: AppOptionValue | null): void {
  if (value === 'NORMAL_GENERATION' || value === 'STYLE_REPLICATION') {
    library.setMode(value as GenerationMode)
  }
}

function openCreateGroup(): void {
  groupDialogMode.value = 'create'
  editingGroup.value = null
  groupDialogShow.value = true
}

function openRenameGroup(group: TemplateGroup): void {
  groupDialogMode.value = 'rename'
  editingGroup.value = group
  groupDialogShow.value = true
}

function saveGroup(input: TemplateGroupInput): void {
  if (groupDialogMode.value === 'create') {
    library.createGroup(input)
  } else if (editingGroup.value) {
    library.renameGroup(editingGroup.value.id, input.name)
  }
  groupDialogShow.value = false
  editingGroup.value = null
}

function confirmDelete(): void {
  const target = pendingDelete.value
  if (!target) return
  if (target.type === 'group') library.deleteGroup(target.group.id)
  else library.deleteTemplate(target.template.id)
  pendingDelete.value = null
}

function duplicateTemplate(templateId: string): void {
  if (library.duplicateTemplate(templateId)) message.success('已复制')
}

function saveTemplate(input: PromptTemplateInput): void {
  if (!selectedTemplate.value) return
  library.updateTemplate(selectedTemplate.value.id, input)
  message.success('已保存')
}
</script>

<template>
  <AiManagementToolbar label="模板库工具栏">
    <AppInput
      v-model="searchDraft"
      width="lg"
      placeholder="搜索模板"
      clearable
      aria-label="搜索模板"
      @update:model-value="autoSearch.onInput"
      @compositionstart="autoSearch.onCompositionStart"
      @compositionend="autoSearch.onCompositionEnd(searchDraft)"
      @keyup.enter="autoSearch.onEnter($event)"
    />
    <template #actions>
      <AppSelect
        class="template-library-mode-select"
        :model-value="activeMode"
        :options="modeOptions"
        width="sm"
        aria-label="生成模式"
        @update:model-value="updateMode"
      />
      <AppButton tone="primary" @click="openCreateGroup">
        <Plus :size="16" />
        新建模板组
      </AppButton>
    </template>
  </AiManagementToolbar>

  <AiManagementLayout label="模板库">
    <ThreePaneWorkbench>
      <template #left>
        <TemplateGroupSidebar
          :groups="visibleGroups"
          :selected-group-id="selectedGroupId"
          @create="openCreateGroup"
          @select="library.selectGroup"
          @rename="openRenameGroup"
          @remove="pendingDelete = { type: 'group', group: $event }"
        />
      </template>

      <template #main>
        <TemplateSequenceList
          :group="selectedGroup"
          :templates="visibleTemplates"
          :role-filter="roleFilter"
          :selected-template-id="selectedTemplateId"
          :page="currentPage"
          :page-size="pageSize"
          :item-count="totalTemplates"
          @create="library.createTemplate"
          @filter="library.setRoleFilter"
          @select="library.selectTemplate"
          @move="library.moveTemplate"
          @duplicate="duplicateTemplate"
          @remove="pendingDelete = { type: 'template', template: $event }"
          @update:page="library.setPage"
          @update:page-size="library.setPageSize"
        />
      </template>

      <template #right>
        <TemplateEditor
          v-if="selectedTemplate"
          :key="selectedTemplate.id"
          :template="selectedTemplate"
          @close="library.selectTemplate(null)"
          @save="saveTemplate"
        />
        <TemplateGroupSettings
          v-else-if="selectedGroup"
          :group="selectedGroup"
          @update:enabled="library.setGroupEnabled(selectedGroup.id, $event)"
        />
        <EmptyState v-else description="暂无模板组" />
      </template>
    </ThreePaneWorkbench>
  </AiManagementLayout>

  <TemplateGroupFormDialog
    :show="groupDialogShow"
    :mode="groupDialogMode"
    :group="editingGroup"
    :current-mode="activeMode"
    @update:show="groupDialogShow = $event"
    @save="saveGroup"
  />

  <AppDialog
    :show="Boolean(pendingDelete)"
    :title="deleteDialogTitle"
    size="sm"
    positive-text="删除"
    @update:show="pendingDelete = null"
    @confirm="confirmDelete"
  >
    {{ deleteDialogText }}
  </AppDialog>
</template>

<style scoped>
.template-library-mode-select {
  width: var(--field-width-sm);
  flex: 0 0 var(--field-width-sm);
}
</style>
