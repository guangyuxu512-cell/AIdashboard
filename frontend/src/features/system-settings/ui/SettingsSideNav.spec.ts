import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import SettingsSideNav from './SettingsSideNav.vue'

const push = vi.fn()
const authState = vi.hoisted(() => ({
  isAccessAdministrator: true,
  isSuperAccount: true,
  allowedModuleCodes: new Set(['settings']),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ name: 'audit-logs' }),
  useRouter: () => ({ push }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => authState,
}))

describe('SettingsSideNav', () => {
  it('uses the existing authorized settings routes as vertical navigation', async () => {
    const wrapper = mount(SettingsSideNav)
    const buttons = wrapper.findAll('button')

    expect(wrapper.get('nav').attributes('aria-label')).toBe('系统设置')
    expect(buttons.map((button) => button.text())).toEqual([
      '用户与权限',
      '操作日志',
      'AI 模型管理',
      '通知配置',
    ])
    expect(wrapper.get('button[aria-current="page"]').text()).toBe('操作日志')

    await buttons[0]?.trigger('click')

    expect(push).toHaveBeenCalledWith({ name: 'access-management' })
  })

  it('hides administrator settings from ordinary members', () => {
    authState.isAccessAdministrator = false

    const wrapper = mount(SettingsSideNav)

    expect(wrapper.findAll('button').map((button) => button.text())).toEqual([
      '通知配置',
    ])
    authState.isAccessAdministrator = true
  })
})
