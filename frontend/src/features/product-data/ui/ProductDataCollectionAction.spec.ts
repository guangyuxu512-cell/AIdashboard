import { flushPromises, mount } from '@vue/test-utils'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { describe, expect, it, vi } from 'vitest'
import { AppButton } from '@/shared/ui'
import { createUnavailableProductDataSource } from '../api/product-data-source'
import type { ProductDataCollection, ProductDataSource } from '../model/types'
import ProductDataCollectionAction from './ProductDataCollectionAction.vue'

function receipt(
  status: ProductDataCollection['status'] = 'failed',
): ProductDataCollection {
  return {
    id: 'synthetic-generation',
    period: '1d',
    startDate: '2026-01-01',
    endDate: '2026-01-01',
    status,
    stage: status === 'succeeded' ? 'complete' : 'platform_response',
    receivedPages: 0,
    expectedTotal: null,
    receivedTotal: null,
    pagesComplete: status === 'succeeded',
    rawCompleteRows: null,
    unitCompleteRows: null,
    failureCode: status === 'failed' ? 'PLATFORM_TIMEOUT' : null,
    leaseExpired: false,
    createdAt: '2026-01-02T00:00:00Z',
    startedAt: null,
    finishedAt: null,
    publishedAt: null,
  }
}
function source(): ProductDataSource {
  return {
    ...createUnavailableProductDataSource(),
    available: true,
    groupsAvailable: false,
    collect: vi.fn(async () => receipt()),
    collection: vi.fn(async () => receipt()),
  }
}
function render(dataSource: ProductDataSource, enabled = true) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  const wrapper = mount(ProductDataCollectionAction, {
    props: {
      source: dataSource,
      contextKey: 'synthetic:team',
      shopId: 'synthetic-shop',
      period: '1d',
      enabled,
    },
    global: {
      plugins: [[VueQueryPlugin, { queryClient }]],
      stubs: {
        NTooltip: { template: '<span><slot name="trigger"/><slot/></span>' },
      },
    },
  })
  return {
    wrapper,
    queryClient,
    dispose: () => {
      wrapper.unmount()
      queryClient.clear()
    },
  }
}
describe('Explicit Product Data collection action', () => {
  it('does not collect on mount, disabled click, query or missing shop', async () => {
    const dataSource = source(),
      { wrapper, dispose } = render(dataSource, false)
    try {
      await flushPromises()
      wrapper.findComponent(AppButton).vm.$emit('click')
      await flushPromises()
      expect(dataSource.collect).not.toHaveBeenCalled()
      expect(wrapper.findComponent(AppButton).props('disabled')).toBe(true)
      await wrapper.setProps({ enabled: true, shopId: null })
      wrapper.findComponent(AppButton).vm.$emit('click')
      expect(dataSource.collect).not.toHaveBeenCalled()
    } finally {
      dispose()
    }
  })
  it('guards same-frame double clicks and reuses the exact key after an unconfirmed submission', async () => {
    const dataSource = source()
    let reject!: (error: Error) => void
    vi.mocked(dataSource.collect!).mockImplementationOnce(
      () =>
        new Promise((_, failure) => {
          reject = failure
        }),
    )
    const { wrapper, dispose } = render(dataSource)
    try {
      wrapper.findComponent(AppButton).vm.$emit('click')
      wrapper.findComponent(AppButton).vm.$emit('click')
      await flushPromises()
      expect(dataSource.collect).toHaveBeenCalledTimes(1)
      const first = vi.mocked(dataSource.collect!).mock.calls[0]![0]
      reject(new Error('synthetic submission not confirmed'))
      await flushPromises()
      expect(wrapper.text()).toContain('提交未确认')
      wrapper.findComponent(AppButton).vm.$emit('click')
      await flushPromises()
      expect(vi.mocked(dataSource.collect!).mock.calls[1]![0]).toEqual(first)
      wrapper.findComponent(AppButton).vm.$emit('click')
      await flushPromises()
      expect(
        vi.mocked(dataSource.collect!).mock.calls[2]![0].submissionKey,
      ).not.toBe(first.submissionKey)
    } finally {
      dispose()
    }
  })
  it('reads the precise receipt and invalidates facts after success without another POST', async () => {
    const dataSource = source()
    vi.mocked(dataSource.collect!).mockResolvedValue(receipt('running'))
    vi.mocked(dataSource.collection!).mockResolvedValue(receipt('succeeded'))
    const { wrapper, queryClient, dispose } = render(dataSource)
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    try {
      wrapper.findComponent(AppButton).vm.$emit('click')
      await flushPromises()
      expect(dataSource.collect).toHaveBeenCalledTimes(1)
      expect(dataSource.collection).toHaveBeenCalledExactlyOnceWith(
        'synthetic-generation',
      )
      expect(wrapper.text()).toContain('采集完成')
      expect(invalidate).toHaveBeenCalledWith({
        queryKey: ['product-data', 'synthetic:team'],
      })
    } finally {
      dispose()
    }
  })
  it('a receipt read failure only allows explicit GET retry, not a new collection', async () => {
    const dataSource = source()
    vi.mocked(dataSource.collect!).mockResolvedValue(receipt('running'))
    vi.mocked(dataSource.collection!).mockRejectedValueOnce(
      new Error('synthetic receipt not confirmed'),
    )
    const { wrapper, dispose } = render(dataSource)
    try {
      wrapper.findComponent(AppButton).vm.$emit('click')
      await flushPromises()
      expect(wrapper.text()).toContain('回执读取未完成')
      wrapper.findComponent(AppButton).vm.$emit('click')
      await flushPromises()
      expect(dataSource.collection).toHaveBeenCalledTimes(2)
      expect(dataSource.collect).toHaveBeenCalledTimes(1)
    } finally {
      dispose()
    }
  })
  it('does not show a late result in a changed shop or actor context', async () => {
    const dataSource = source()
    let resolve!: (value: ProductDataCollection) => void
    vi.mocked(dataSource.collect!).mockImplementationOnce(
      () =>
        new Promise((success) => {
          resolve = success
        }),
    )
    const { wrapper, dispose } = render(dataSource)
    try {
      wrapper.findComponent(AppButton).vm.$emit('click')
      await flushPromises()
      await wrapper.setProps({ contextKey: 'other:team', shopId: 'other-shop' })
      resolve(receipt('succeeded'))
      await flushPromises()
      expect(wrapper.text()).not.toContain('采集完成')
      expect(dataSource.collection).not.toHaveBeenCalled()
    } finally {
      dispose()
    }
  })
})
