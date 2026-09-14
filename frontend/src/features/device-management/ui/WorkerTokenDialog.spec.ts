import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AppButton from '@/shared/ui/AppButton.vue'
import AppDialog from '@/shared/ui/AppDialog.vue'
import AppInput from '@/shared/ui/AppInput.vue'

import WorkerTokenDialog from './WorkerTokenDialog.vue'

const success = vi.fn()
const error = vi.fn()
const consoleWarn = vi
  .spyOn(console, 'warn')
  .mockImplementation(() => undefined)

vi.mock('naive-ui', async (importOriginal) => {
  const actual = await importOriginal<typeof import('naive-ui')>()
  return {
    ...actual,
    useMessage: () => ({ success, error }),
  }
})

describe('WorkerTokenDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setClipboard(vi.fn().mockResolvedValue(undefined))
  })

  it('masks then copies the one-time token through the clipboard API', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    setClipboard(writeText)
    const wrapper = mountTokenDialog()

    const dialog = wrapper.findComponent(AppDialog)
    expect(dialog.props('showNegative')).toBe(false)
    const description = dialog.vm.$slots.description?.({})
    expect(description?.[0]?.children).toContain('仅本次显示')
    const input = wrapper.findComponent(AppInput)
    expect(input.props('type')).toBe('password')
    expect(input.props('disabled')).toBe(true)

    await findButton(wrapper, '复制').trigger('click')
    await flushPromises()

    expect(writeText).toHaveBeenCalledWith('ccw_one_time_secret')
    expect(success).toHaveBeenCalledWith('Worker Token 已复制')
  })

  it('reveals a readonly, selectable token for manual copy', async () => {
    const wrapper = mountTokenDialog()

    await findButton(wrapper, '显示').trigger('click')

    const input = wrapper.findComponent(AppInput)
    expect(input.props('type')).toBe('text')
    expect(input.props('disabled')).toBe(false)
    expect(input.props('readonly')).toBe(true)
  })

  it('keeps the dialog open and de-duplicates a clipboard permission failure', async () => {
    const writeText = vi
      .fn()
      .mockRejectedValue(
        new DOMException('permission denied', 'NotAllowedError'),
      )
    setClipboard(writeText)
    const wrapper = mountTokenDialog()
    const copyButton = findButton(wrapper, '复制')

    await copyButton.trigger('click')
    await flushPromises()
    await copyButton.trigger('click')
    await flushPromises()

    expect(writeText).toHaveBeenCalledTimes(2)
    expect(error).toHaveBeenCalledOnce()
    expect(error).toHaveBeenCalledWith(
      'Worker Token 复制失败，请点击“显示”后手动选中复制',
    )
    expect(consoleWarn).toHaveBeenCalledOnce()
    expect(consoleWarn).toHaveBeenCalledWith(
      '[worker-token-copy] clipboard write failed',
      'NotAllowedError',
    )
    expect(consoleWarn.mock.calls.flat()).not.toContain('ccw_one_time_secret')
    expect(wrapper.findComponent(AppDialog).props('show')).toBe(true)
  })

  it('reports an unavailable clipboard API without closing the dialog', async () => {
    setClipboard(undefined)
    const wrapper = mountTokenDialog()

    await findButton(wrapper, '复制').trigger('click')
    await flushPromises()

    expect(error).toHaveBeenCalledWith(
      'Worker Token 复制失败，请点击“显示”后手动选中复制',
    )
    expect(consoleWarn).toHaveBeenCalledWith(
      '[worker-token-copy] clipboard write failed',
      'TypeError',
    )
    expect(wrapper.findComponent(AppDialog).props('show')).toBe(true)
  })

  it('does not log an arbitrary clipboard exception name', async () => {
    const unknownError = new Error('clipboard write failed')
    unknownError.name = 'ccw_one_time_secret'
    setClipboard(vi.fn().mockRejectedValue(unknownError))
    const wrapper = mountTokenDialog()

    await findButton(wrapper, '复制').trigger('click')
    await flushPromises()

    expect(consoleWarn).toHaveBeenCalledWith(
      '[worker-token-copy] clipboard write failed',
      'Error',
    )
    expect(consoleWarn.mock.calls.flat()).not.toContain('ccw_one_time_secret')
  })

  it('prevents overlapping clipboard writes while a copy is in progress', async () => {
    let resolveWrite: (() => void) | undefined
    const writeText = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveWrite = resolve
        }),
    )
    setClipboard(writeText)
    const wrapper = mountTokenDialog()
    const copyButton = findButton(wrapper, '复制')

    await copyButton.trigger('click')
    await copyButton.trigger('click')

    expect(writeText).toHaveBeenCalledOnce()
    expect(copyButton.props('loading')).toBe(true)

    resolveWrite?.()
    await flushPromises()

    expect(success).toHaveBeenCalledOnce()
    expect(findButton(wrapper, '复制').props('loading')).toBe(false)
  })
})

function mountTokenDialog() {
  return shallowMount(WorkerTokenDialog, {
    props: { show: true, token: 'ccw_one_time_secret' },
    global: { renderStubDefaultSlot: true },
  })
}

function findButton(
  wrapper: ReturnType<typeof mountTokenDialog>,
  label: string,
) {
  const button = wrapper
    .findAllComponents(AppButton)
    .find((candidate) => candidate.text() === label)
  if (!button) throw new Error(`Button not found: ${label}`)
  return button
}

function setClipboard(writeText: ReturnType<typeof vi.fn> | undefined): void {
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: writeText ? { writeText } : undefined,
  })
}
