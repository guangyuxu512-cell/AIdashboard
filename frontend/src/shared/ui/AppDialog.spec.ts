import { mount } from '@vue/test-utils'
import { NModal } from 'naive-ui'
import { nextTick } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import AppDialog from './AppDialog.vue'

describe('AppDialog', () => {
  it('constrains the card to the viewport and delegates scrolling to its body', () => {
    const wrapper = mount(AppDialog, {
      props: {
        show: false,
        title: '参数配置',
      },
    })

    const modal = wrapper.findComponent(NModal)

    expect(modal.props('contentScrollable')).toBe(true)
    expect(modal.vm.$attrs.style).toMatchObject({
      maxHeight: 'var(--dialog-max-height)',
    })
    expect(modal.vm.$attrs.class).toContain('app-dialog')
  })

  it('offers opt-in extra-large and workspace layouts without changing the default', () => {
    const regular = mount(AppDialog, {
      props: { show: false, title: '普通弹窗' },
    })
    const extraLarge = mount(AppDialog, {
      props: { show: false, title: '资料预览', size: 'xl' },
    })
    const workspace = mount(AppDialog, {
      props: {
        show: false,
        title: '商品编辑',
        size: 'workspace',
        contentScrollable: false,
      },
    })

    expect(regular.findComponent(NModal).vm.$attrs.style).toMatchObject({
      width: 'var(--dialog-width-md)',
    })
    expect(extraLarge.findComponent(NModal).vm.$attrs.style).toMatchObject({
      width: 'var(--dialog-width-xl)',
      maxWidth: 'calc(100vw - var(--space-8))',
    })
    const workspaceModal = workspace.findComponent(NModal)
    expect(workspaceModal.vm.$attrs.style).toMatchObject({
      width: 'var(--dialog-width-workspace)',
      maxWidth: 'var(--dialog-width-workspace)',
      height: 'var(--dialog-height-workspace)',
      maxHeight: 'var(--dialog-height-workspace)',
    })
    expect(workspaceModal.props('contentScrollable')).toBe(false)
    expect(workspaceModal.vm.$attrs.class).toContain('app-dialog--workspace')
  })

  it('explains why the positive action is disabled', async () => {
    vi.useFakeTimers()
    const wrapper = mount(AppDialog, {
      props: {
        show: true,
        title: '运行应用',
        positiveDisabled: true,
        positiveDisabledReason: '请填写关键词',
        to: document.body,
      },
      attachTo: document.body,
    })

    expect(wrapper.findComponent({ name: 'Tooltip' }).exists()).toBe(true)
    const trigger = document.querySelector('.app-dialog__disabled-action')
    expect(trigger).not.toBeNull()
    trigger?.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }))
    vi.runAllTimers()
    await nextTick()
    expect(document.body.textContent).toContain('请填写关键词')
    wrapper.unmount()
    vi.useRealTimers()
  })
})
