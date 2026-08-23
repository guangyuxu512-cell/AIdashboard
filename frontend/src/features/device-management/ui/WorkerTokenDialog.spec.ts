import { shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AppButton from '@/shared/ui/AppButton.vue'
import AppDialog from '@/shared/ui/AppDialog.vue'

import WorkerTokenDialog from './WorkerTokenDialog.vue'

const success = vi.fn()

vi.mock('naive-ui', async (importOriginal) => {
  const actual = await importOriginal<typeof import('naive-ui')>()
  return {
    ...actual,
    useMessage: () => ({ success, error: vi.fn() }),
  }
})

describe('WorkerTokenDialog', () => {
  beforeEach(() => {
    success.mockReset()
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    })
  })

  it('masks, copies and only exposes the one-time token in the issue dialog', async () => {
    const wrapper = shallowMount(WorkerTokenDialog, {
      props: { show: true, token: 'ccw_one_time_secret' },
      global: { renderStubDefaultSlot: true },
    })

    const dialog = wrapper.findComponent(AppDialog)
    expect(dialog.props('showNegative')).toBe(false)
    const description = dialog.vm.$slots.description?.({})
    expect(description?.[0]?.children).toContain('仅本次显示')
    const buttons = wrapper.findAllComponents(AppButton)
    await buttons.find((button) => button.text() === '复制')?.trigger('click')

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      'ccw_one_time_secret',
    )
    expect(success).toHaveBeenCalledOnce()
  })
})
