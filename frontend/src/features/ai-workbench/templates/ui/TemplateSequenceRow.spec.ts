import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { createTemplateGroupFixtures } from '../__fixtures__/template-groups.fixture'

import TemplateSequenceRow from './TemplateSequenceRow.vue'
import templateSequenceRowSource from './TemplateSequenceRow.vue?raw'

describe('TemplateSequenceRow', () => {
  it('shows role and size in fixed lightweight text slots', async () => {
    const templates = createTemplateGroupFixtures()[0]!.templates
    const template = templates[0]!
    const wrapper = mount(TemplateSequenceRow, {
      props: {
        template,
        active: false,
        canMoveUp: false,
        canMoveDown: true,
      },
    })

    expect(wrapper.get('.template-sequence-row__size').text()).toBe('1:1')
    expect(wrapper.get('.template-sequence-row__role').text()).toBe('主图')
    expect(wrapper.attributes('data-output-role')).toBe('MAIN_IMAGE')

    const detailTemplate = templates.find(
      (candidate) => candidate.outputRole === 'DETAIL_IMAGE',
    )!
    await wrapper.setProps({ template: detailTemplate })
    expect(wrapper.get('.template-sequence-row__role').text()).toBe('详情')
    expect(wrapper.get('.template-sequence-row__size').text()).toBe('3:4')
    expect(wrapper.attributes('data-output-role')).toBe('DETAIL_IMAGE')

    expect(templateSequenceRowSource).toContain('appearance="dot"')
    expect(wrapper.get('.status-tag__dot').attributes()).toMatchObject({
      'aria-label': detailTemplate.enabled ? '启用' : '停用',
      role: 'status',
    })
    expect(templateSequenceRowSource).toContain('CompactEntityRow')
  })
})
