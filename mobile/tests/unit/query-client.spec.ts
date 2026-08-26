import { flushPromises, mount } from '@vue/test-utils'
import { onlineManager, VueQueryPlugin } from '@tanstack/vue-query'
import { defineComponent, h, nextTick } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createMobileQueryClient } from '@/app/providers/query-client'
import {
  getActiveTaskQueryOptions,
  useTaskDetailQuery,
  useTaskListQuery,
} from '@/entities/task'
import { apiClient } from '@/shared/api'
import { getOnlineRefetchInterval } from '@/shared/utils/query-connectivity'

describe('createMobileQueryClient', () => {
  afterEach(() => {
    onlineManager.setOnline(true)
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('uses deterministic foundation defaults', () => {
    const queryClient = createMobileQueryClient()
    const defaults = queryClient.getDefaultOptions()

    expect(defaults.queries?.networkMode).toBe('always')
    expect(defaults.queries?.retry).toBe(false)
    expect(defaults.queries?.refetchOnReconnect).toBe(true)
    expect(defaults.queries?.refetchOnWindowFocus).toBe(false)
    expect(defaults.mutations?.retry).toBe(false)
  })

  it('runs and settles an initial request even when the browser reports offline', async () => {
    onlineManager.setOnline(false)
    const queryClient = createMobileQueryClient()
    const queryFn = vi.fn().mockRejectedValue(new Error('网络不可用'))

    await expect(
      queryClient.fetchQuery({ queryKey: ['offline-terminal'], queryFn }),
    ).rejects.toThrow('网络不可用')

    expect(queryFn).toHaveBeenCalledOnce()
    expect(queryClient.getQueryState(['offline-terminal'])).toMatchObject({
      status: 'error',
      fetchStatus: 'idle',
    })
  })

  it('disables recurring background requests while offline and restores them on reconnect', () => {
    const activeOptions = getActiveTaskQueryOptions('device-1')

    expect(activeOptions.refetchInterval.value).toBe(5_000)
    expect(getOnlineRefetchInterval(15_000)).toBe(15_000)

    onlineManager.setOnline(false)
    expect(activeOptions.refetchInterval.value).toBe(false)
    expect(getOnlineRefetchInterval(15_000)).toBe(false)

    onlineManager.setOnline(true)
    expect(activeOptions.refetchInterval.value).toBe(5_000)
  })

  it('reactively stops Task List and Detail timers offline and resumes them on reconnect', async () => {
    vi.useFakeTimers()
    const get = vi.spyOn(apiClient, 'get').mockImplementation((path) => {
      if (path === 'tasks') {
        return Promise.resolve({
          status: 200,
          data: { items: [], total: 0, page: 1, page_size: 20 },
        })
      }
      return Promise.resolve({
        status: 200,
        data: {
          task_id: 'task-1',
          target_device_id: 'device-1',
          shop_ids: [],
          asset_ids: [],
          skill_id: 'skill-1',
          execution_display_name: '同步订单',
          status: 'running',
          input: {},
          result: null,
          error_code: null,
          error_message: null,
          lease_until: null,
          started_at: '2026-08-27T00:00:00.000Z',
          finished_at: null,
          runtime_events_purged_at: null,
          created_at: '2026-08-27T00:00:00.000Z',
          updated_at: '2026-08-27T00:00:00.000Z',
        },
      })
    })
    const queryClient = createMobileQueryClient()
    const component = defineComponent({
      setup() {
        useTaskListQuery({})
        useTaskDetailQuery('task-1')
        return () => h('div')
      },
    })
    const wrapper = mount(component, {
      global: {
        plugins: [[VueQueryPlugin, { queryClient }]],
      },
    })
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(2)

    onlineManager.setOnline(false)
    await nextTick()
    await vi.advanceTimersByTimeAsync(6_000)
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(2)

    onlineManager.setOnline(true)
    await nextTick()
    await flushPromises()
    expect(get.mock.calls.length).toBeGreaterThan(2)

    wrapper.unmount()
    queryClient.clear()
  })
})
