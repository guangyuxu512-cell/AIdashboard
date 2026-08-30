import { h } from 'vue'
import { NConfigProvider } from 'naive-ui'
import { flushPromises, mount } from '@vue/test-utils'
import {
  createMemoryHistory,
  createRouter,
  type RouteRecordRaw,
} from 'vue-router'
import { describe, expect, it } from 'vitest'

import { AI_WORKBENCH_NAVIGATION } from '../model/routes'
import AiGeneratePage from '@/pages/ai-workbench/AiGeneratePage.vue'

const routes: RouteRecordRaw[] = AI_WORKBENCH_NAVIGATION.map((route) => ({
  name: route.name,
  path: route.path,
  component: { template: '<div />' },
}))

describe('AI workbench shell', () => {
  it('uses route navigation as page identity without explanatory copy', async () => {
    const router = createRouter({ history: createMemoryHistory(), routes })
    await router.push('/ai-workbench/generate')

    const wrapper = mount(
      {
        render: () =>
          h(NConfigProvider, null, {
            default: () => h(AiGeneratePage),
          }),
      },
      { global: { plugins: [router] } },
    )

    expect(wrapper.findAll('.ai-module-navigation button')).toHaveLength(3)
    expect(wrapper.text()).toContain('AI生图')
    expect(wrapper.text()).toContain('素材库')
    expect(wrapper.text()).toContain('模板库')
    expect(wrapper.find('h1').exists()).toBe(false)
    expect(wrapper.find('.page-header').exists()).toBe(false)
    expect(wrapper.text()).not.toContain(
      '组合商品素材、生成模式与输出类型，创建电商视觉内容。',
    )
    expect(wrapper.text()).not.toContain('添加素材并完成创作设置后')
    expect(wrapper.text()).toContain('暂无生成结果')

    await wrapper
      .get('.ai-module-navigation button[aria-label="素材库"]')
      .trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('ai-workbench-assets')
  })
})
