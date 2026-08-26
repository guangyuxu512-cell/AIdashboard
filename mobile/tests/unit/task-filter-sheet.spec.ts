import { mount, type VueWrapper } from '@vue/test-utils'
import { nextTick, ref } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createDefaultTaskFilterDraft } from '@/features/task-center'

const deviceQueryMock = vi.hoisted(() => ({
  current: null as unknown,
}))
const mountedWrappers: VueWrapper[] = []

vi.mock('@/entities/device', () => ({
  useDeviceListQuery: () => deviceQueryMock.current,
}))

import { TaskFilterSheet } from '@/features/task-center'

function createDeviceQuery(options: {
  data?: {
    pages: Array<{
      items: Array<{
        device_id: string
        display_name: string
      }>
    }>
  }
  error?: Error
  isError?: boolean
}) {
  return {
    data: ref(options.data),
    error: ref(options.error ?? null),
    isError: ref(options.isError ?? false),
    isFetchNextPageError: ref(false),
    isFetchingNextPage: ref(false),
    hasNextPage: ref(false),
    isPending: ref(false),
    fetchNextPage: vi.fn(),
    refetch: vi.fn(),
  }
}

async function openDevicePicker() {
  const wrapper = mount(TaskFilterSheet, {
    props: {
      modelValue: true,
      filters: createDefaultTaskFilterDraft(new Date(2026, 7, 26, 12, 0, 0)),
    },
    attachTo: document.body,
  })
  mountedWrappers.push(wrapper)
  await wrapper.get('[data-testid="device-filter"]').trigger('click')
  await nextTick()
  return wrapper
}

describe('device filter error states', () => {
  afterEach(async () => {
    for (const wrapper of mountedWrappers.splice(0)) wrapper.unmount()
    // Vant safe-area placeholders schedule three post-mount measurements.
    // Let them settle while jsdom's window is still available.
    await new Promise((resolve) => setTimeout(resolve, 350))
    document.body.innerHTML = ''
  })

  it('shows a full retry state when the initial device request fails', async () => {
    const query = createDeviceQuery({
      error: new Error('设备初始加载失败'),
      isError: true,
    })
    deviceQueryMock.current = query
    const wrapper = await openDevicePicker()

    expect(wrapper.text()).toContain('设备初始加载失败')
    const retry = wrapper.get('.task-filter-sheet__device-popup button')
    expect(retry.text()).toContain('重新加载')
    await retry.trigger('click')
    expect(query.refetch).toHaveBeenCalledOnce()
  })

  it('keeps successful device options during a background failure', async () => {
    deviceQueryMock.current = createDeviceQuery({
      data: {
        pages: [
          {
            items: [{ device_id: 'device-1', display_name: '仓库手机' }],
          },
        ],
      },
      error: new Error('设备后台刷新失败'),
      isError: true,
    })
    const wrapper = await openDevicePicker()

    expect(wrapper.text()).toContain('设备后台刷新失败，已保留当前设备选项')
    expect(wrapper.text()).toContain('仓库手机')
    expect(wrapper.text()).not.toContain('重新加载')
  })
})
