import { shallowMount } from '@vue/test-utils'
import { NDropdown } from 'naive-ui'
import { describe, expect, it } from 'vitest'

import { createTemplateGroupFixtures } from '../__fixtures__/template-groups.fixture'
import { useAiTemplatesVisualMock } from '../model/useAiTemplatesVisualMock'
import PaginationBar from '@/shared/components/PaginationBar.vue'

import TemplateSequenceList from './TemplateSequenceList.vue'
import TemplateSequenceRow from './TemplateSequenceRow.vue'

function createWrapper(options: { page?: number } = {}) {
  const library = useAiTemplatesVisualMock(createTemplateGroupFixtures())
  const page = options.page ?? 1
  library.setPage(page)
  const group = library.selectedGroup.value!

  return shallowMount(TemplateSequenceList, {
    props: {
      group,
      templates: library.visibleTemplates.value,
      roleFilter: 'ALL',
      selectedTemplateId: null,
      page,
      pageSize: 20,
      itemCount: group.templates.length,
    },
    global: { renderStubDefaultSlot: true },
  })
}

describe('TemplateSequenceList', () => {
  it('renders one continuous paged list with interactive whole-group role totals', () => {
    const wrapper = createWrapper()
    const roleFilters = wrapper.get('[aria-label="模板角色筛选"]')

    expect(wrapper.findAll('.template-sequence-section')).toHaveLength(0)
    expect(roleFilters.get('[data-role-filter="ALL"]').text()).toBe('全部 24')
    expect(roleFilters.get('[data-role-filter="MAIN_IMAGE"]').text()).toBe(
      '主图 12',
    )
    expect(roleFilters.get('[data-role-filter="DETAIL_IMAGE"]').text()).toBe(
      '详情 12',
    )
    expect(
      roleFilters.get('[data-role-filter="ALL"]').attributes('aria-pressed'),
    ).toBe('true')
    expect(wrapper.findAllComponents(PaginationBar)).toHaveLength(1)
    expect(wrapper.findAllComponents(TemplateSequenceRow)).toHaveLength(20)
    expect(
      wrapper
        .findAllComponents(TemplateSequenceRow)
        .map((row) => row.props('template').outputRole),
    ).toEqual([
      ...Array.from({ length: 12 }, () => 'MAIN_IMAGE'),
      ...Array.from({ length: 8 }, () => 'DETAIL_IMAGE'),
    ])
  })

  it('creates either role from the single add menu', () => {
    const wrapper = createWrapper()
    const addButton = wrapper.get('[aria-label="添加模板"]')
    const dropdown = wrapper.findComponent(NDropdown)

    expect(addButton.attributes('aria-label')).toBe('添加模板')
    expect(dropdown.props('options')).toEqual([
      { key: 'MAIN_IMAGE', label: '主图' },
      { key: 'DETAIL_IMAGE', label: '详情' },
    ])
    dropdown.vm.$emit('select', 'MAIN_IMAGE')
    dropdown.vm.$emit('select', 'DETAIL_IMAGE')
    expect(wrapper.emitted('create')).toEqual([
      ['MAIN_IMAGE'],
      ['DETAIL_IMAGE'],
    ])
  })

  it('emits compact role filters and exposes the active state', async () => {
    const wrapper = createWrapper()

    await wrapper.get('[data-role-filter="MAIN_IMAGE"]').trigger('click')
    await wrapper.get('[data-role-filter="DETAIL_IMAGE"]').trigger('click')
    await wrapper.get('[data-role-filter="ALL"]').trigger('click')
    expect(wrapper.emitted('filter')).toEqual([
      ['MAIN_IMAGE'],
      ['DETAIL_IMAGE'],
      ['ALL'],
    ])

    await wrapper.setProps({ roleFilter: 'DETAIL_IMAGE' })
    expect(
      wrapper
        .get('[data-role-filter="DETAIL_IMAGE"]')
        .attributes('aria-pressed'),
    ).toBe('true')
    expect(
      wrapper.get('[data-role-filter="ALL"]').attributes('aria-pressed'),
    ).toBe('false')
  })

  it('keeps page and search results flat while retaining whole-group totals', async () => {
    const wrapper = createWrapper({ page: 2 })
    const pageRows = wrapper.findAllComponents(TemplateSequenceRow)

    expect(wrapper.findAll('.template-sequence-section')).toHaveLength(0)
    expect(pageRows).toHaveLength(4)
    expect(
      pageRows.every(
        (row) => row.props('template').outputRole === 'DETAIL_IMAGE',
      ),
    ).toBe(true)
    expect(wrapper.get('[data-role-filter="ALL"]').text()).toBe('全部 24')
    expect(wrapper.get('[data-role-filter="MAIN_IMAGE"]').text()).toBe(
      '主图 12',
    )
    expect(wrapper.get('[data-role-filter="DETAIL_IMAGE"]').text()).toBe(
      '详情 12',
    )

    const group = createTemplateGroupFixtures()[0]!
    const detailResult = group.templates.find(
      (template) => template.outputRole === 'DETAIL_IMAGE',
    )!
    await wrapper.setProps({
      templates: [detailResult],
      page: 1,
      itemCount: 1,
    })
    expect(wrapper.findAllComponents(TemplateSequenceRow)).toHaveLength(1)
    expect(wrapper.findAll('.template-sequence-section')).toHaveLength(0)
    expect(wrapper.get('[data-role-filter="ALL"]').text()).toBe('全部 24')
    expect(wrapper.get('[data-role-filter="MAIN_IMAGE"]').text()).toBe(
      '主图 12',
    )
    expect(wrapper.get('[data-role-filter="DETAIL_IMAGE"]').text()).toBe(
      '详情 12',
    )
  })

  it('disables movement only at the full role boundaries', () => {
    const wrapper = createWrapper()
    const rows = wrapper.findAllComponents(TemplateSequenceRow)
    const mainRows = rows.filter(
      (row) => row.props('template').outputRole === 'MAIN_IMAGE',
    )
    const detailRows = rows.filter(
      (row) => row.props('template').outputRole === 'DETAIL_IMAGE',
    )

    expect(mainRows[0]!.props()).toMatchObject({
      canMoveUp: false,
      canMoveDown: true,
    })
    expect(mainRows.at(-1)!.props('canMoveDown')).toBe(false)
    expect(detailRows[0]!.props('canMoveUp')).toBe(false)
    expect(detailRows[0]!.props('canMoveDown')).toBe(true)
  })
})
