import { shallowMount } from '@vue/test-utils'
import { NFormItem } from 'naive-ui'
import { describe, expect, it } from 'vitest'

import { createTemplateGroupFixtures } from '../__fixtures__/template-groups.fixture'
import { AppSelect } from '@/shared/ui'

import TemplateEditor from './TemplateEditor.vue'

describe('TemplateEditor', () => {
  it('keeps output role out of the editor while preserving editable size', () => {
    const template = createTemplateGroupFixtures()[0]!.templates[0]!
    const wrapper = shallowMount(TemplateEditor, {
      props: { template },
      global: { renderStubDefaultSlot: true },
    })

    expect(wrapper.text()).not.toContain('输出类型')
    expect(
      wrapper
        .findAllComponents(AppSelect)
        .map((component) => component.attributes('aria-label')),
    ).toEqual(['输出格式', '比例'])
    const labels = wrapper
      .findAllComponents(NFormItem)
      .map((component) => component.props('label'))
    expect(labels).toContain('提示词')
    expect(labels).not.toContain('Prompt')
    expect(labels).not.toContain('Negative Prompt')
    expect('negativePrompt' in template).toBe(false)
  })
})
