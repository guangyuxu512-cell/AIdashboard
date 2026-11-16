import { computed, ref, watch } from 'vue'

import type {
  GenerationMode,
  PromptTemplate,
  PromptTemplateInput,
  TemplateOutputRole,
  TemplateGroup,
  TemplateGroupInput,
  TemplateRoleFilter,
} from './types'

export const TEMPLATE_LIBRARY_PAGE_SIZE = 20

interface VisualMockDependencies {
  now?: () => string
}

const TEMPLATE_ROLE_ORDER: Record<TemplateOutputRole, number> = {
  MAIN_IMAGE: 0,
  DETAIL_IMAGE: 1,
}

function cloneGroups(groups: readonly TemplateGroup[]): TemplateGroup[] {
  return groups.map((group) => {
    const clonedGroup: TemplateGroup = {
      ...group,
      templates: group.templates.map((template) => ({
        ...template,
        variables: [...template.variables],
      })),
    }
    normalizeSortOrder(clonedGroup)
    return clonedGroup
  })
}

function matches(value: string, query: string): boolean {
  return value.toLocaleLowerCase().includes(query)
}

function normalizeSortOrder(group: TemplateGroup): void {
  group.templates.sort(
    (left, right) =>
      TEMPLATE_ROLE_ORDER[left.outputRole] -
        TEMPLATE_ROLE_ORDER[right.outputRole] ||
      left.sortOrder - right.sortOrder,
  )
  assignSortOrder(group)
}

function assignSortOrder(group: TemplateGroup): void {
  group.templates.forEach((template, index) => {
    template.sortOrder = index + 1
  })
}

export function useAiTemplatesVisualMock(
  initialGroups: readonly TemplateGroup[],
  dependencies: VisualMockDependencies = {},
) {
  const groups = ref<TemplateGroup[]>(cloneGroups(initialGroups))
  const activeMode = ref<GenerationMode>('NORMAL_GENERATION')
  const searchQuery = ref('')
  const roleFilter = ref<TemplateRoleFilter>('ALL')
  const selectedGroupId = ref<string | null>(
    groups.value.find((group) => group.mode === activeMode.value)?.id ?? null,
  )
  const selectedTemplateId = ref<string | null>(null)
  const currentPage = ref(1)
  const pageSize = ref(TEMPLATE_LIBRARY_PAGE_SIZE)
  let localIdSequence = 0

  const now = dependencies.now ?? (() => new Date().toISOString())

  const visibleGroups = computed(() => {
    const query = searchQuery.value.trim().toLocaleLowerCase()
    return groups.value.filter(
      (group) =>
        group.mode === activeMode.value &&
        (!query ||
          matches(group.name, query) ||
          group.templates.some((template) => matches(template.name, query))),
    )
  })

  const selectedGroup = computed(
    () =>
      groups.value.find((group) => group.id === selectedGroupId.value) ?? null,
  )

  const filteredTemplates = computed(() => {
    const group = selectedGroup.value
    if (!group) return []
    const templates = [...group.templates].sort(
      (left, right) => left.sortOrder - right.sortOrder,
    )
    const query = searchQuery.value.trim().toLocaleLowerCase()
    const searchedTemplates =
      !query || matches(group.name, query)
        ? templates
        : templates.filter((template) => matches(template.name, query))
    if (roleFilter.value === 'ALL') return searchedTemplates
    return searchedTemplates.filter(
      (template) => template.outputRole === roleFilter.value,
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

  const selectedTemplate = computed(() => {
    if (!selectedGroup.value || !selectedTemplateId.value) return null
    return (
      selectedGroup.value.templates.find(
        (template) => template.id === selectedTemplateId.value,
      ) ?? null
    )
  })

  watch(
    visibleGroups,
    (nextGroups) => {
      if (!nextGroups.some((group) => group.id === selectedGroupId.value)) {
        selectedGroupId.value = nextGroups[0]?.id ?? null
      }
    },
    { flush: 'sync' },
  )

  watch(
    selectedGroupId,
    () => {
      roleFilter.value = 'ALL'
      currentPage.value = 1
      selectedTemplateId.value = null
    },
    { flush: 'sync' },
  )

  watch(
    searchQuery,
    () => {
      currentPage.value = 1
      selectedTemplateId.value = null
    },
    { flush: 'sync' },
  )

  function setMode(mode: GenerationMode): void {
    if (mode === activeMode.value) return
    activeMode.value = mode
    roleFilter.value = 'ALL'
    selectedGroupId.value = visibleGroups.value[0]?.id ?? null
    selectedTemplateId.value = null
    currentPage.value = 1
  }

  function selectGroup(groupId: string): void {
    if (!visibleGroups.value.some((group) => group.id === groupId)) return
    selectedGroupId.value = groupId
  }

  function selectTemplate(templateId: string | null): void {
    if (templateId === null) {
      selectedTemplateId.value = null
      return
    }
    if (
      !selectedGroup.value?.templates.some((item) => item.id === templateId)
    ) {
      return
    }
    selectedTemplateId.value = templateId
  }

  function setRoleFilter(filter: TemplateRoleFilter): void {
    roleFilter.value = filter
    currentPage.value = 1
    selectedTemplateId.value = null
  }

  function createGroup(input: TemplateGroupInput): TemplateGroup {
    localIdSequence += 1
    const timestamp = now()
    const group: TemplateGroup = {
      id: `visual-template-group-${localIdSequence}`,
      name: input.name.trim(),
      mode: input.mode,
      enabled: true,
      templates: [],
      createdAt: timestamp,
      updatedAt: timestamp,
    }
    groups.value.push(group)
    activeMode.value = input.mode
    searchQuery.value = ''
    selectedGroupId.value = group.id
    selectedTemplateId.value = null
    currentPage.value = 1
    return group
  }

  function renameGroup(groupId: string, name: string): void {
    const group = groups.value.find((candidate) => candidate.id === groupId)
    if (!group) return
    group.name = name.trim()
    group.updatedAt = now()
  }

  function deleteGroup(groupId: string): void {
    const visibleIndex = visibleGroups.value.findIndex(
      (group) => group.id === groupId,
    )
    const groupIndex = groups.value.findIndex((group) => group.id === groupId)
    if (groupIndex < 0) return
    const wasSelected = selectedGroupId.value === groupId
    const nextSelectedGroupId = wasSelected
      ? (visibleGroups.value[visibleIndex + 1]?.id ??
        visibleGroups.value[visibleIndex - 1]?.id ??
        null)
      : selectedGroupId.value
    if (wasSelected) selectedGroupId.value = nextSelectedGroupId
    groups.value.splice(groupIndex, 1)
    if (!wasSelected) return
    selectedTemplateId.value = null
    currentPage.value = 1
  }

  function setGroupEnabled(groupId: string, enabled: boolean): void {
    const group = groups.value.find((candidate) => candidate.id === groupId)
    if (!group) return
    group.enabled = enabled
    group.updatedAt = now()
  }

  function createTemplate(
    outputRole: TemplateOutputRole,
  ): PromptTemplate | null {
    const group = selectedGroup.value
    if (!group) return null
    localIdSequence += 1
    const timestamp = now()
    const template: PromptTemplate = {
      id: `visual-prompt-template-${localIdSequence}`,
      name: '新建模板',
      enabled: true,
      outputRole,
      outputFormat: 'SINGLE',
      size: outputRole === 'MAIN_IMAGE' ? '1:1' : '3:4',
      count: 1,
      variables: ['product_name'],
      prompt: '{product_name}',
      sortOrder: group.templates.length + 1,
      createdAt: timestamp,
      updatedAt: timestamp,
    }
    group.templates.push(template)
    normalizeSortOrder(group)
    group.updatedAt = timestamp
    searchQuery.value = ''
    if (roleFilter.value !== 'ALL' && roleFilter.value !== outputRole) {
      roleFilter.value = outputRole
    }
    selectedTemplateId.value = template.id
    const filteredIndex = filteredTemplates.value.findIndex(
      (candidate) => candidate.id === template.id,
    )
    currentPage.value = Math.max(
      1,
      Math.ceil((filteredIndex + 1) / pageSize.value),
    )
    return template
  }

  function updateTemplate(
    templateId: string,
    input: PromptTemplateInput,
  ): void {
    const group = selectedGroup.value
    const template = group?.templates.find((item) => item.id === templateId)
    if (!group || !template) return
    const variables = [
      ...new Set(input.variables.map((value) => value.trim()).filter(Boolean)),
    ]
    Object.assign(template, {
      name: input.name.trim(),
      enabled: input.enabled,
      outputFormat: input.outputFormat,
      size: input.size,
      count: input.count,
      variables,
      prompt: input.prompt.trim(),
      updatedAt: now(),
    })
    group.updatedAt = template.updatedAt
  }

  function deleteTemplate(templateId: string): void {
    const group = selectedGroup.value
    if (!group) return
    const index = group.templates.findIndex(
      (template) => template.id === templateId,
    )
    if (index < 0) return
    group.templates.splice(index, 1)
    normalizeSortOrder(group)
    group.updatedAt = now()
    if (selectedTemplateId.value === templateId) {
      selectedTemplateId.value = null
    }
    currentPage.value = Math.min(currentPage.value, pageCount.value)
  }

  function duplicateTemplate(templateId: string): PromptTemplate | null {
    const group = selectedGroup.value
    if (!group) return null
    normalizeSortOrder(group)
    const index = group.templates.findIndex(
      (template) => template.id === templateId,
    )
    if (index < 0) return null
    const source = group.templates[index]
    if (!source) return null
    localIdSequence += 1
    const timestamp = now()
    const copy: PromptTemplate = {
      ...source,
      id: `visual-prompt-template-${localIdSequence}`,
      name: `${source.name} 副本`,
      variables: [...source.variables],
      sortOrder: source.sortOrder + 1,
      createdAt: timestamp,
      updatedAt: timestamp,
    }
    group.templates.splice(index + 1, 0, copy)
    assignSortOrder(group)
    group.updatedAt = timestamp
    selectedTemplateId.value = copy.id
    const filteredIndex = filteredTemplates.value.findIndex(
      (candidate) => candidate.id === copy.id,
    )
    currentPage.value = Math.max(
      1,
      Math.ceil((filteredIndex + 1) / pageSize.value),
    )
    return copy
  }

  function moveTemplate(templateId: string, direction: 'up' | 'down'): void {
    const group = selectedGroup.value
    if (!group) return
    normalizeSortOrder(group)
    const template = group.templates.find((item) => item.id === templateId)
    if (!template) return
    const roleTemplates = group.templates.filter(
      (item) => item.outputRole === template.outputRole,
    )
    const roleIndex = roleTemplates.findIndex((item) => item.id === templateId)
    const targetRoleIndex = direction === 'up' ? roleIndex - 1 : roleIndex + 1
    const target = roleTemplates[targetRoleIndex]
    if (!target) return
    const index = group.templates.findIndex((item) => item.id === template.id)
    const targetIndex = group.templates.findIndex(
      (item) => item.id === target.id,
    )
    group.templates[index] = target
    group.templates[targetIndex] = template
    assignSortOrder(group)
    group.updatedAt = now()
    const filteredIndex = filteredTemplates.value.findIndex(
      (candidate) => candidate.id === template.id,
    )
    currentPage.value = Math.max(
      1,
      Math.ceil((filteredIndex + 1) / pageSize.value),
    )
  }

  function setPage(page: number): void {
    const nextPage = Math.min(Math.max(1, page), pageCount.value)
    if (nextPage === currentPage.value) return
    currentPage.value = nextPage
    selectedTemplateId.value = null
  }

  function setPageSize(value: number): void {
    if (!Number.isInteger(value) || value <= 0 || value === pageSize.value) {
      return
    }
    pageSize.value = value
    currentPage.value = 1
    selectedTemplateId.value = null
  }

  return {
    groups,
    activeMode,
    searchQuery,
    roleFilter,
    visibleGroups,
    selectedGroupId,
    selectedGroup,
    selectedTemplateId,
    selectedTemplate,
    filteredTemplates,
    visibleTemplates,
    totalTemplates,
    currentPage,
    pageSize,
    pageCount,
    setMode,
    setRoleFilter,
    selectGroup,
    selectTemplate,
    createGroup,
    renameGroup,
    deleteGroup,
    setGroupEnabled,
    createTemplate,
    updateTemplate,
    deleteTemplate,
    duplicateTemplate,
    moveTemplate,
    setPage,
    setPageSize,
  }
}
