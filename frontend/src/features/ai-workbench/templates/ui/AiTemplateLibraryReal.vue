<script setup lang="ts">
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { Plus } from '@lucide/vue'
import type { SelectOption } from 'naive-ui'
import { useMessage } from 'naive-ui'
import { computed, ref, watch } from 'vue'

import { aiWorkbenchApi, aiWorkbenchQueryKeys } from '@/entities/ai-workbench'
import {
  AiManagementLayout,
  AiManagementToolbar,
} from '@/features/ai-workbench'
import EmptyState from '@/shared/components/EmptyState.vue'
import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'
import ThreePaneWorkbench from '@/shared/components/ThreePaneWorkbench.vue'
import { getErrorMessage } from '@/shared/api'
import { AppButton, AppDialog, AppInput, AppSelect } from '@/shared/ui'
import type { AppOptionValue } from '@/shared/ui/types'

import {
  GENERATION_MODE_META,
  type GenerationMode,
  type PromptTemplate,
  type PromptTemplateInput,
  type TemplateGroup,
  type TemplateGroupInput,
  type TemplateOutputRole,
  type TemplateRoleFilter,
} from '../model/types'
import { mapTemplateGroup } from '../../real-api/model/mappers'
import TemplateEditor from './TemplateEditor.vue'
import TemplateGroupFormDialog from './TemplateGroupFormDialog.vue'
import TemplateGroupSettings from './TemplateGroupSettings.vue'
import TemplateGroupSidebar from './TemplateGroupSidebar.vue'
import TemplateSequenceList from './TemplateSequenceList.vue'

type PendingDelete =
  | { type: 'group'; group: TemplateGroup }
  | { type: 'template'; template: PromptTemplate }

const message = useMessage()
const queryClient = useQueryClient()
const activeMode = ref<GenerationMode>('NORMAL_GENERATION')
const searchQuery = ref('')
const roleFilter = ref<TemplateRoleFilter>('ALL')
const selectedGroupId = ref<string | null>(null)
const selectedTemplateId = ref<string | null>(null)
const currentPage = ref(1)
const pageSize = ref(20)
const groupDialogShow = ref(false)
const groupDialogMode = ref<'create' | 'rename'>('create')
const editingGroup = ref<TemplateGroup | null>(null)
const pendingDelete = ref<PendingDelete | null>(null)

const groupsQuery = useQuery({
  queryKey: aiWorkbenchQueryKeys.templates,
  queryFn: async () => {
    const summaries = await aiWorkbenchApi.listAllTemplateGroups()
    return Promise.all(
      summaries.map((group) =>
        aiWorkbenchApi.getTemplateGroup(group.template_group_id),
      ),
    )
  },
  select: (groups) => groups.map(mapTemplateGroup),
})

const actionMutation = useMutation({
  mutationFn: (action: () => Promise<void>) => action(),
  onSuccess: () =>
    queryClient.invalidateQueries({ queryKey: aiWorkbenchQueryKeys.templates }),
})

const groups = computed(() => groupsQuery.data.value ?? [])
const visibleGroups = computed(() => {
  const query = searchQuery.value.trim().toLocaleLowerCase()
  return groups.value.filter(
    (group) =>
      group.mode === activeMode.value &&
      (!query ||
        group.name.toLocaleLowerCase().includes(query) ||
        group.templates.some((template) =>
          template.name.toLocaleLowerCase().includes(query),
        )),
  )
})
const selectedGroup = computed(
  () =>
    groups.value.find((group) => group.id === selectedGroupId.value) ?? null,
)
const selectedTemplate = computed(
  () =>
    selectedGroup.value?.templates.find(
      (template) => template.id === selectedTemplateId.value,
    ) ?? null,
)
const filteredTemplates = computed(() => {
  const group = selectedGroup.value
  if (!group) return []
  const query = searchQuery.value.trim().toLocaleLowerCase()
  return [...group.templates]
    .sort((left, right) => left.sortOrder - right.sortOrder)
    .filter(
      (template) =>
        (!query ||
          group.name.toLocaleLowerCase().includes(query) ||
          template.name.toLocaleLowerCase().includes(query)) &&
        (roleFilter.value === 'ALL' ||
          template.outputRole === roleFilter.value),
    )
})
const totalTemplates = computed(() => filteredTemplates.value.length)
const pageCount = computed(() =>
  Math.max(1, Math.ceil(totalTemplates.value / pageSize.value)),
)
const visibleTemplates = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredTemplates.value.slice(start, start + pageSize.value)
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
  return target.type === 'group'
    ? `确认删除模板组“${target.group.name}”？`
    : `确认删除模板“${target.template.name}”？`
})

watch(
  visibleGroups,
  (next) => {
    if (!next.some((group) => group.id === selectedGroupId.value)) {
      selectedGroupId.value = next[0]?.id ?? null
    }
  },
  { immediate: true, flush: 'sync' },
)
watch(selectedGroupId, () => {
  roleFilter.value = 'ALL'
  currentPage.value = 1
  selectedTemplateId.value = null
})
watch(searchQuery, () => {
  currentPage.value = 1
  selectedTemplateId.value = null
})

async function execute(action: () => Promise<void>, success?: string) {
  try {
    await actionMutation.mutateAsync(action)
    if (success) message.success(success)
  } catch (error) {
    message.error(getErrorMessage(error))
  }
}

function updateMode(value: AppOptionValue | null): void {
  if (value !== 'NORMAL_GENERATION' && value !== 'STYLE_REPLICATION') return
  activeMode.value = value
  roleFilter.value = 'ALL'
  currentPage.value = 1
  selectedTemplateId.value = null
}

function selectGroup(groupId: string): void {
  // A row can be selected again while its template editor is open. Vue will
  // not notify the selectedGroupId watcher for an identical id, so clear the
  // child selection explicitly and return the right pane to group settings.
  selectedGroupId.value = groupId
  selectedTemplateId.value = null
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
  const editing = editingGroup.value
  groupDialogShow.value = false
  editingGroup.value = null
  void execute(
    async () => {
      if (groupDialogMode.value === 'create') {
        const created = await aiWorkbenchApi.createTemplateGroup({
          name: input.name.trim(),
          mode: input.mode,
        })
        activeMode.value = input.mode
        searchQuery.value = ''
        selectedGroupId.value = created.template_group_id
        return
      }
      if (editing) {
        await aiWorkbenchApi.updateTemplateGroup(editing.id, {
          name: input.name.trim(),
        })
      }
    },
    groupDialogMode.value === 'create' ? '模板组已创建' : '模板组已更新',
  )
}

function setGroupEnabled(groupId: string, enabled: boolean): void {
  void execute(
    async () => {
      await aiWorkbenchApi.updateTemplateGroup(groupId, { enabled })
    },
    enabled ? '模板组已启用' : '模板组已停用',
  )
}

function createTemplate(outputRole: TemplateOutputRole): void {
  const groupId = selectedGroupId.value
  if (!groupId) return
  void execute(async () => {
    const updated = await aiWorkbenchApi.createPromptTemplate(groupId, {
      name: outputRole === 'MAIN_IMAGE' ? '新建主图模板' : '新建详情模板',
      enabled: true,
      output_role: outputRole,
      output_format: 'SINGLE',
      size: outputRole === 'MAIN_IMAGE' ? '1:1' : '3:4',
      count: 1,
      variables: [],
      prompt:
        outputRole === 'MAIN_IMAGE'
          ? '生成清晰的商品主图'
          : '生成清晰的商品详情图',
    })
    selectedTemplateId.value =
      [...updated.prompt_templates]
        .sort((left, right) => right.sort_order - left.sort_order)
        .find((template) => template.output_role === outputRole)
        ?.prompt_template_id ?? null
    roleFilter.value = roleFilter.value === 'ALL' ? 'ALL' : outputRole
  }, '模板已创建')
}

function saveTemplate(input: PromptTemplateInput): void {
  const groupId = selectedGroupId.value
  const templateId = selectedTemplateId.value
  if (!groupId || !templateId) return
  void execute(async () => {
    await aiWorkbenchApi.updatePromptTemplate(groupId, templateId, {
      name: input.name.trim(),
      enabled: input.enabled,
      output_format: input.outputFormat,
      size: input.size,
      count: input.count,
      variables: input.variables.map((value) => value.trim()).filter(Boolean),
      prompt: input.prompt.trim(),
    })
  }, '已保存')
}

function duplicateTemplate(templateId: string): void {
  const groupId = selectedGroupId.value
  if (!groupId) return
  void execute(async () => {
    const updated = await aiWorkbenchApi.duplicatePromptTemplate(
      groupId,
      templateId,
    )
    const source = updated.prompt_templates.find(
      (template) => template.prompt_template_id === templateId,
    )
    const copy = updated.prompt_templates.find(
      (template) =>
        template.prompt_template_id !== templateId &&
        template.output_role === source?.output_role &&
        template.name === `${source?.name} 副本`,
    )
    selectedTemplateId.value = copy?.prompt_template_id ?? templateId
  }, '已复制')
}

function moveTemplate(templateId: string, direction: 'up' | 'down'): void {
  const group = selectedGroup.value
  if (!group) return
  const template = group.templates.find((item) => item.id === templateId)
  if (!template) return
  const ids = group.templates
    .filter((item) => item.outputRole === template.outputRole)
    .sort((left, right) => left.sortOrder - right.sortOrder)
    .map((item) => item.id)
  const index = ids.indexOf(templateId)
  const target = direction === 'up' ? index - 1 : index + 1
  if (target < 0 || target >= ids.length) return
  ;[ids[index], ids[target]] = [ids[target]!, ids[index]!]
  void execute(async () => {
    await aiWorkbenchApi.reorderPromptTemplates(
      group.id,
      template.outputRole,
      ids,
    )
  })
}

function confirmDelete(): void {
  const target = pendingDelete.value
  pendingDelete.value = null
  if (!target) return
  if (target.type === 'group') {
    void execute(async () => {
      await aiWorkbenchApi.deleteTemplateGroup(target.group.id)
      if (selectedGroupId.value === target.group.id)
        selectedGroupId.value = null
    }, '模板组已删除')
    return
  }
  const groupId = selectedGroupId.value
  if (!groupId) return
  void execute(async () => {
    await aiWorkbenchApi.deletePromptTemplate(groupId, target.template.id)
    if (selectedTemplateId.value === target.template.id) {
      selectedTemplateId.value = null
    }
  }, '模板已删除')
}

function setRoleFilter(value: TemplateRoleFilter): void {
  roleFilter.value = value
  currentPage.value = 1
  selectedTemplateId.value = null
}

function setPage(value: number): void {
  currentPage.value = Math.min(Math.max(1, value), pageCount.value)
  selectedTemplateId.value = null
}

function setPageSize(value: number): void {
  pageSize.value = value
  currentPage.value = 1
  selectedTemplateId.value = null
}
</script>

<template>
  <AiManagementToolbar label="模板库工具栏">
    <AppInput
      v-model="searchQuery"
      width="lg"
      placeholder="搜索模板"
      clearable
      aria-label="搜索模板"
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
    <LoadingState
      v-if="groupsQuery.isPending.value"
      description="正在加载模板"
    />
    <ErrorState
      v-else-if="groupsQuery.isError.value"
      :description="getErrorMessage(groupsQuery.error.value)"
      retryable
      @retry="groupsQuery.refetch()"
    />
    <ThreePaneWorkbench v-else>
      <template #left>
        <TemplateGroupSidebar
          :groups="visibleGroups"
          :selected-group-id="selectedGroupId"
          @create="openCreateGroup"
          @select="selectGroup"
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
          @create="createTemplate"
          @filter="setRoleFilter"
          @select="selectedTemplateId = $event"
          @move="moveTemplate"
          @duplicate="duplicateTemplate"
          @remove="pendingDelete = { type: 'template', template: $event }"
          @update:page="setPage"
          @update:page-size="setPageSize"
        />
      </template>

      <template #right>
        <TemplateEditor
          v-if="selectedTemplate"
          :key="selectedTemplate.id"
          :template="selectedTemplate"
          @close="selectedTemplateId = null"
          @save="saveTemplate"
        />
        <TemplateGroupSettings
          v-else-if="selectedGroup"
          :group="selectedGroup"
          @update:enabled="setGroupEnabled(selectedGroup.id, $event)"
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
