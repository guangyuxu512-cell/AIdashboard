import { describe, expect, it } from 'vitest'

import { createTemplateGroupFixtures } from '../__fixtures__/template-groups.fixture'
import type {
  PromptTemplate,
  PromptTemplateInput,
  TemplateOutputRole,
} from './types'
import { useAiTemplatesVisualMock } from './useAiTemplatesVisualMock'

const NOW = '2026-08-31T08:00:00.000Z'

function createLibrary() {
  return useAiTemplatesVisualMock(createTemplateGroupFixtures(), {
    now: () => NOW,
  })
}

function expectStableRoleOrder(templates: readonly PromptTemplate[]): void {
  expect(templates.map((template) => template.sortOrder)).toEqual(
    Array.from({ length: templates.length }, (_, index) => index + 1),
  )
  const roles = templates.map((template) => template.outputRole)
  const firstDetailIndex = roles.indexOf('DETAIL_IMAGE')
  if (firstDetailIndex < 0) return
  expect(
    roles.slice(firstDetailIndex).every((role) => role === 'DETAIL_IMAGE'),
  ).toBe(true)
}

function roleIds(
  templates: readonly PromptTemplate[],
  role: TemplateOutputRole,
): string[] {
  return templates
    .filter((template) => template.outputRole === role)
    .map((template) => template.id)
}

describe('useAiTemplatesVisualMock', () => {
  it('uses one shared generation config and preserves fixture restrictions', () => {
    const template = createTemplateGroupFixtures()[0]!.templates[0]!

    expect('negativePrompt' in template).toBe(false)
    expect(template.prompt).toContain('避免模糊、变形、多余文字和低清晰度')
    expect(template).toMatchObject({
      outputRole: 'MAIN_IMAGE',
      outputFormat: 'SINGLE',
      size: '1:1',
      count: 1,
      variables: ['product_name', 'selling_points'],
    })
  })

  it('strictly isolates groups by generation mode and resets the template selection', () => {
    const library = createLibrary()

    expect(library.activeMode.value).toBe('NORMAL_GENERATION')
    expect(library.roleFilter.value).toBe('ALL')
    expect(library.visibleGroups.value).toHaveLength(4)
    expect(
      library.visibleGroups.value.every(
        (group) => group.mode === 'NORMAL_GENERATION',
      ),
    ).toBe(true)
    expect(
      library.visibleGroups.value.some(
        (group) => group.id === 'style-competitor-a',
      ),
    ).toBe(false)

    library.selectTemplate('normal-standard-main-1')
    expect(library.selectedTemplate.value?.name).toBe('极简白底')
    library.setRoleFilter('DETAIL_IMAGE')
    library.setPage(2)

    library.setMode('STYLE_REPLICATION')
    expect(library.selectedTemplate.value).toBeNull()
    expect(library.roleFilter.value).toBe('ALL')
    expect(library.currentPage.value).toBe(1)
    expect(library.selectedGroup.value?.id).toBe('style-competitor-a')
    expect(library.visibleGroups.value).toHaveLength(3)
    expect(
      library.visibleGroups.value.every(
        (group) => group.mode === 'STYLE_REPLICATION',
      ),
    ).toBe(true)
    expect(
      library.visibleGroups.value.some(
        (group) => group.id === 'normal-standard-set',
      ),
    ).toBe(false)
  })

  it('creates, renames, disables and deletes groups without changing their mode', () => {
    const library = createLibrary()
    const sourceGroup = library.selectedGroup.value!
    const sourceTemplateIds = sourceGroup.templates.map(
      (template) => template.id,
    )

    library.setGroupEnabled(sourceGroup.id, false)
    expect(sourceGroup.enabled).toBe(false)
    expect(sourceGroup.templates.map((template) => template.id)).toEqual(
      sourceTemplateIds,
    )

    const created = library.createGroup({
      name: '  新复刻模板组  ',
      mode: 'STYLE_REPLICATION',
    })
    expect(created).toMatchObject({
      name: '新复刻模板组',
      mode: 'STYLE_REPLICATION',
      enabled: true,
      templates: [],
    })
    expect(library.activeMode.value).toBe('STYLE_REPLICATION')
    expect(library.selectedGroupId.value).toBe(created.id)
    expect(library.selectedGroup.value?.templates).toHaveLength(0)

    library.renameGroup(created.id, '  新复刻模板组 B  ')
    expect(library.selectedGroup.value).toMatchObject({
      id: created.id,
      name: '新复刻模板组 B',
      mode: 'STYLE_REPLICATION',
      updatedAt: NOW,
    })
    expect('setGroupMode' in library).toBe(false)

    library.deleteGroup(created.id)
    expect(library.groups.value.some((group) => group.id === created.id)).toBe(
      false,
    )
    expect(library.selectedGroup.value?.mode).toBe('STYLE_REPLICATION')
  })

  it('selects the next valid group or empty state after deleting the current group', () => {
    const library = createLibrary()
    library.setMode('STYLE_REPLICATION')
    const initialIds = library.visibleGroups.value.map((group) => group.id)

    library.deleteGroup(initialIds[0]!)
    expect(library.selectedGroupId.value).toBe(initialIds[1])

    for (const group of [...library.visibleGroups.value]) {
      library.deleteGroup(group.id)
    }
    expect(library.visibleGroups.value).toEqual([])
    expect(library.selectedGroup.value).toBeNull()
    expect(library.selectedTemplate.value).toBeNull()
  })

  it('creates templates from their section with role-specific size defaults', () => {
    const library = createLibrary()
    library.selectGroup('normal-minimal-main')
    const initialCount = library.selectedGroup.value!.templates.length
    const mainTemplate = library.createTemplate('MAIN_IMAGE')!

    expect(mainTemplate).toMatchObject({
      name: '新建模板',
      enabled: true,
      outputRole: 'MAIN_IMAGE',
      outputFormat: 'SINGLE',
      size: '1:1',
      count: 1,
      variables: ['product_name'],
      prompt: '{product_name}',
    })
    expect(library.selectedTemplateId.value).toBe(mainTemplate.id)
    expect(library.selectedGroup.value!.templates).toHaveLength(
      initialCount + 1,
    )

    const detailTemplate = library.createTemplate('DETAIL_IMAGE')!
    expect(detailTemplate).toMatchObject({
      name: '新建模板',
      outputRole: 'DETAIL_IMAGE',
      size: '3:4',
    })
    expect(library.selectedTemplateId.value).toBe(detailTemplate.id)
    expectStableRoleOrder(library.selectedGroup.value!.templates)
  })

  it('edits size independently without changing output role', () => {
    const library = createLibrary()
    library.selectGroup('normal-minimal-main')
    const created = library.createTemplate('DETAIL_IMAGE')!

    const update: PromptTemplateInput = {
      name: '  详情改版  ',
      enabled: false,
      outputFormat: 'COLLAGE_2X2',
      size: '1:1',
      count: 8,
      variables: [' product_name ', 'selling_points', 'product_name'],
      prompt: '  使用 {product_name} 和 {selling_points}  ',
    }
    library.updateTemplate(created.id, update)
    expect(library.selectedTemplate.value).toMatchObject({
      id: created.id,
      name: '详情改版',
      enabled: false,
      outputRole: 'DETAIL_IMAGE',
      outputFormat: 'COLLAGE_2X2',
      size: '1:1',
      count: 8,
      variables: ['product_name', 'selling_points'],
      prompt: '使用 {product_name} 和 {selling_points}',
      updatedAt: NOW,
    })

    const mainTemplate = library.createTemplate('MAIN_IMAGE')!
    library.updateTemplate(mainTemplate.id, {
      ...update,
      name: '主图宽幅',
      size: '16:9',
    })
    expect(mainTemplate).toMatchObject({
      name: '主图宽幅',
      outputRole: 'MAIN_IMAGE',
      size: '16:9',
    })
    expectStableRoleOrder(library.selectedGroup.value!.templates)
  })

  it('duplicates role and size, then renumbers continuously after deletion', () => {
    const library = createLibrary()
    library.selectGroup('normal-minimal-main')
    const initialCount = library.selectedGroup.value!.templates.length
    const created = library.createTemplate('DETAIL_IMAGE')!
    library.updateTemplate(created.id, {
      name: '详情宽幅',
      enabled: false,
      outputFormat: 'COLLAGE_2X2',
      size: '16:9',
      count: 8,
      variables: ['product_name', 'selling_points'],
      prompt: '使用 {product_name} 和 {selling_points}',
    })

    const duplicate = library.duplicateTemplate(created.id)!
    expect(duplicate.id).not.toBe(created.id)
    expect(duplicate).toMatchObject({
      name: '详情宽幅 副本',
      enabled: false,
      outputRole: 'DETAIL_IMAGE',
      outputFormat: 'COLLAGE_2X2',
      size: '16:9',
      count: 8,
      variables: ['product_name', 'selling_points'],
      prompt: '使用 {product_name} 和 {selling_points}',
      sortOrder: created.sortOrder + 1,
    })
    expect(duplicate.variables).not.toBe(created.variables)
    expect(library.selectedTemplateId.value).toBe(duplicate.id)

    library.deleteTemplate(duplicate.id)
    expect(library.selectedTemplate.value).toBeNull()
    expect(library.selectedGroup.value!.templates).toHaveLength(
      initialCount + 1,
    )
    expectStableRoleOrder(library.selectedGroup.value!.templates)
  })

  it('moves templates only within the same role and keeps one continuous order', () => {
    const library = createLibrary()
    const group = library.selectedGroup.value!
    const initialMainIds = roleIds(group.templates, 'MAIN_IMAGE')
    const initialDetailIds = roleIds(group.templates, 'DETAIL_IMAGE')
    const firstMainId = initialMainIds[0]!
    const secondMainId = initialMainIds[1]!
    const lastMainId = initialMainIds.at(-1)!
    const firstDetailId = initialDetailIds[0]!
    const secondDetailId = initialDetailIds[1]!

    library.moveTemplate(firstMainId, 'down')
    expect(roleIds(group.templates, 'MAIN_IMAGE').slice(0, 2)).toEqual([
      secondMainId,
      firstMainId,
    ])
    expect(roleIds(group.templates, 'DETAIL_IMAGE')).toEqual(initialDetailIds)
    expectStableRoleOrder(group.templates)

    library.moveTemplate(firstMainId, 'up')
    expect(roleIds(group.templates, 'MAIN_IMAGE').slice(0, 2)).toEqual([
      firstMainId,
      secondMainId,
    ])

    library.moveTemplate(lastMainId, 'down')
    expect(roleIds(group.templates, 'MAIN_IMAGE')).toEqual(initialMainIds)
    expect(roleIds(group.templates, 'DETAIL_IMAGE')[0]).toBe(firstDetailId)

    library.moveTemplate(firstDetailId, 'down')
    expect(roleIds(group.templates, 'MAIN_IMAGE')).toEqual(initialMainIds)
    expect(roleIds(group.templates, 'DETAIL_IMAGE').slice(0, 2)).toEqual([
      secondDetailId,
      firstDetailId,
    ])
    expectStableRoleOrder(group.templates)

    library.moveTemplate(firstDetailId, 'up')
    expect(roleIds(group.templates, 'DETAIL_IMAGE')).toEqual(initialDetailIds)

    library.moveTemplate(firstDetailId, 'up')
    expect(roleIds(group.templates, 'MAIN_IMAGE')).toEqual(initialMainIds)
    expect(roleIds(group.templates, 'DETAIL_IMAGE')).toEqual(initialDetailIds)
    expectStableRoleOrder(group.templates)
  })

  it('uses standard pagination, resets it for context changes and clamps after deletion', () => {
    const library = createLibrary()

    expect(library.pageSize.value).toBe(20)
    expect(library.totalTemplates.value).toBe(24)
    expect(library.pageCount.value).toBe(2)
    expect(library.visibleTemplates.value).toHaveLength(20)

    library.setPage(2)
    expect(library.visibleTemplates.value).toHaveLength(4)
    library.setPageSize(10)
    expect(library.currentPage.value).toBe(1)
    expect(library.pageCount.value).toBe(3)
    expect(library.visibleTemplates.value).toHaveLength(10)

    library.setPage(3)
    library.selectTemplate(library.visibleTemplates.value[0]!.id)
    library.searchQuery.value = '场景扩展 17'
    expect(library.currentPage.value).toBe(1)
    expect(library.selectedTemplate.value).toBeNull()
    expect(library.visibleTemplates.value).toHaveLength(1)

    library.searchQuery.value = '电商标准套图 A'
    expect(library.totalTemplates.value).toBe(24)
    library.searchQuery.value = ''
    library.setPage(3)
    const lastPageTemplates = [...library.visibleTemplates.value]
    expect(lastPageTemplates).toHaveLength(4)
    for (const template of lastPageTemplates) {
      library.deleteTemplate(template.id)
    }
    expect(library.totalTemplates.value).toBe(20)
    expect(library.currentPage.value).toBe(2)
    expect(library.visibleTemplates.value).toHaveLength(10)

    library.selectTemplate(library.visibleTemplates.value[0]!.id)
    library.setRoleFilter('DETAIL_IMAGE')
    library.selectGroup('normal-minimal-main')
    expect(library.currentPage.value).toBe(1)
    expect(library.roleFilter.value).toBe('ALL')
    expect(library.selectedTemplate.value).toBeNull()

    for (const size of [20, 50, 100]) {
      library.setPageSize(size)
      expect(library.pageSize.value).toBe(size)
      expect(library.currentPage.value).toBe(1)
    }
  })

  it('applies search, then role filtering, then pagination', () => {
    const library = createLibrary()

    library.setPageSize(10)
    library.setPage(2)
    library.selectTemplate(library.visibleTemplates.value[0]!.id)
    library.setRoleFilter('MAIN_IMAGE')

    expect(library.roleFilter.value).toBe('MAIN_IMAGE')
    expect(library.currentPage.value).toBe(1)
    expect(library.selectedTemplate.value).toBeNull()
    expect(library.totalTemplates.value).toBe(12)
    expect(library.pageCount.value).toBe(2)
    expect(library.visibleTemplates.value).toHaveLength(10)
    expect(
      library.visibleTemplates.value.every(
        (template) => template.outputRole === 'MAIN_IMAGE',
      ),
    ).toBe(true)

    library.setPage(2)
    expect(library.visibleTemplates.value).toHaveLength(2)

    library.setRoleFilter('DETAIL_IMAGE')
    expect(library.currentPage.value).toBe(1)
    expect(library.totalTemplates.value).toBe(12)
    expect(library.pageCount.value).toBe(2)
    expect(library.visibleTemplates.value).toHaveLength(10)
    expect(
      library.visibleTemplates.value.every(
        (template) => template.outputRole === 'DETAIL_IMAGE',
      ),
    ).toBe(true)

    library.searchQuery.value = '场景扩展'
    expect(library.currentPage.value).toBe(1)
    expect(library.totalTemplates.value).toBe(8)
    expect(library.pageCount.value).toBe(1)
    expect(
      library.visibleTemplates.value.every(
        (template) =>
          template.name.includes('场景扩展') &&
          template.outputRole === 'DETAIL_IMAGE',
      ),
    ).toBe(true)

    library.setRoleFilter('ALL')
    expect(library.currentPage.value).toBe(1)
    expect(library.totalTemplates.value).toBe(17)
    expect(library.pageCount.value).toBe(2)
    expect(library.visibleTemplates.value).toHaveLength(10)
  })

  it('searches group and template names only within the active mode', () => {
    const library = createLibrary()

    library.searchQuery.value = '竞品'
    expect(library.visibleGroups.value).toEqual([])

    library.searchQuery.value = '生活场景套图'
    expect(library.visibleGroups.value.map((group) => group.id)).toEqual([
      'normal-lifestyle-set',
    ])
    expect(library.filteredTemplates.value).toHaveLength(5)

    library.searchQuery.value = '办公场景'
    expect(library.visibleGroups.value.map((group) => group.id)).toEqual([
      'normal-lifestyle-set',
    ])
    expect(
      library.filteredTemplates.value.map((template) => template.name),
    ).toEqual(['办公场景'])
  })
})
