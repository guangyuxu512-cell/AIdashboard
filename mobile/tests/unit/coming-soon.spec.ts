import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import ComingSoonPage from '@/pages/ComingSoonPage.vue'

describe('ComingSoonPage', () => {
  it.each([
    ['/schedules', '定时计划'],
    ['/shops', '店铺'],
    ['/me', '我的'],
  ])(
    'renders %s from route metadata without fake business data',
    async (path, title) => {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: [
          {
            path,
            component: ComingSoonPage,
            meta: {
              title,
              layout: 'main',
              requiresAuth: false,
              permission: null,
            },
          },
        ],
      })
      await router.push(path)
      await router.isReady()

      const wrapper = mount(ComingSoonPage, {
        global: { plugins: [router] },
      })
      await flushPromises()

      expect(wrapper.text()).toBe('功能建设中')
      expect(wrapper.text()).not.toContain(title)
      expect(wrapper.text()).not.toMatch(/管理员|通知数|99\+/)

      wrapper.unmount()
    },
  )
})
