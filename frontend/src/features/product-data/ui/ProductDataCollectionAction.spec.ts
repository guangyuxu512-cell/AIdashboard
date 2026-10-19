import { flushPromises, mount } from '@vue/test-utils'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AppButton } from '@/shared/ui'
import { createUnavailableProductDataSource } from '../api/product-data-source'
import type {
  ProductDataCollection,
  ProductDataCollectionBatch,
  ProductDataSource,
} from '../model/types'
import ProductDataCollectionAction from './ProductDataCollectionAction.vue'

const ACTIVE_BATCH_ID = '00000000-0000-4000-8000-000000000001'

function collection(
  id: string,
  status: ProductDataCollection['status'] = 'pending',
): ProductDataCollection {
  return {
    id,
    period: '7d',
    startDate: '2026-01-01',
    endDate: '2026-01-07',
    status,
    stage:
      status === 'pending'
        ? 'queued'
        : status === 'succeeded'
          ? 'complete'
          : 'platform_response',
    receivedPages: status === 'succeeded' ? 2 : 0,
    expectedTotal: status === 'succeeded' ? 12 : null,
    receivedTotal: status === 'succeeded' ? 12 : null,
    pagesComplete: status === 'succeeded',
    rawCompleteRows: status === 'succeeded' ? 12 : null,
    unitCompleteRows: status === 'succeeded' ? 12 : null,
    failureCode: status === 'failed' ? 'PLATFORM_TIMEOUT' : null,
    attemptCount: status === 'pending' ? 0 : 1,
    lastHeartbeatAt: status === 'pending' ? null : '2026-01-08T00:00:01Z',
    createdAt: '2026-01-08T00:00:00Z',
    startedAt: status === 'pending' ? null : '2026-01-08T00:00:01Z',
    finishedAt:
      status === 'succeeded' || status === 'failed'
        ? '2026-01-08T00:00:02Z'
        : null,
    publishedAt: status === 'succeeded' ? '2026-01-08T00:00:02Z' : null,
    leaseExpired: false,
  }
}

function batch(
  statuses: ProductDataCollection['status'][] = ['pending', 'pending'],
): ProductDataCollectionBatch {
  const items = statuses.map((status, index) => ({
    shopId: `shop-${index + 1}`,
    shopName: `店铺 ${index + 1}`,
    generation: collection(`generation-${index + 1}`, status),
  }))
  const counts = (status: ProductDataCollection['status']) =>
    items.filter((item) => item.generation.status === status).length
  const pendingCount = counts('pending')
  const runningCount = counts('running')
  const succeededCount = counts('succeeded')
  const failedCount = counts('failed')
  return {
    id: ACTIVE_BATCH_ID,
    status: runningCount
      ? 'running'
      : pendingCount
        ? 'pending'
        : succeededCount === items.length
          ? 'succeeded'
          : failedCount === items.length
            ? 'failed'
            : 'partial',
    totalCount: items.length,
    pendingCount,
    runningCount,
    succeededCount,
    failedCount,
    createdAt: '2026-01-08T00:00:00Z',
    items,
  }
}

function source(): ProductDataSource {
  return {
    ...createUnavailableProductDataSource(),
    available: true,
    groupsAvailable: false,
    collectionShops: vi.fn(async () => [
      { shopId: 'shop-1', shopName: '店铺 1' },
      { shopId: 'shop-2', shopName: '店铺 2' },
    ]),
    collectBatch: vi.fn(async () => batch()),
    collectionBatch: vi.fn(async () => batch(['succeeded', 'succeeded'])),
  }
}

const AppDialogStub = {
  props: ['show', 'positiveDisabled'],
  emits: ['confirm', 'update:show'],
  template:
    '<div v-if="show" data-testid="dialog"><slot/><button data-testid="confirm" :disabled="positiveDisabled" @click="$emit(\'confirm\')">提交更新</button></div>',
}

function render(
  dataSource: ProductDataSource,
  options: { enabled?: boolean; shopId?: string | null } = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  const wrapper = mount(ProductDataCollectionAction, {
    props: {
      source: dataSource,
      contextKey: 'synthetic:team',
      shopId: options.shopId === undefined ? null : options.shopId,
      period: '7d',
      enabled: options.enabled ?? true,
    },
    global: {
      plugins: [[VueQueryPlugin, { queryClient }]],
      stubs: {
        AppDialog: AppDialogStub,
        Tooltip: { template: '<span><slot name="trigger"/><slot/></span>' },
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

async function openAndSubmit(wrapper: ReturnType<typeof mount>) {
  wrapper.findComponent(AppButton).vm.$emit('click')
  await flushPromises()
  await wrapper.get('[data-testid="confirm"]').trigger('click')
  await flushPromises()
}

describe('durable multi-shop Product Data collection action', () => {
  beforeEach(() => window.localStorage.clear())

  it('defaults to every eligible shop and polls one durable batch to completion', async () => {
    const dataSource = source()
    const { wrapper, queryClient, dispose } = render(dataSource)
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    try {
      await openAndSubmit(wrapper)
      expect(dataSource.collectBatch).toHaveBeenCalledExactlyOnceWith({
        shopIds: ['shop-1', 'shop-2'],
        period: '7d',
        submissionKey: expect.any(String),
      })
      expect(dataSource.collectionBatch).toHaveBeenCalledExactlyOnceWith(
        ACTIVE_BATCH_ID,
      )
      expect(wrapper.text()).toContain('采集完成')
      expect(wrapper.text()).toContain('成功 2')
      expect(wrapper.text()).toContain('完成 · 12 件')
      expect(invalidate).toHaveBeenCalledWith({
        queryKey: ['product-data', 'synthetic:team'],
      })
    } finally {
      dispose()
    }
  })

  it('restores an active durable batch after the page is reopened without another POST', async () => {
    const initialSource = source()
    vi.mocked(initialSource.collectionBatch!).mockResolvedValue(
      batch(['running', 'pending']),
    )
    const initial = render(initialSource)
    try {
      await openAndSubmit(initial.wrapper)
      expect(initialSource.collectBatch).toHaveBeenCalledTimes(1)
      expect(
        window.localStorage.getItem(
          'control-center.product-data.active-collection-batch.v1.synthetic:team.7d',
        ),
      ).toBe(ACTIVE_BATCH_ID)
    } finally {
      initial.dispose()
    }

    const restoredSource = source()
    const restored = render(restoredSource)
    try {
      await flushPromises()
      expect(restoredSource.collectionBatch).toHaveBeenCalledExactlyOnceWith(
        ACTIVE_BATCH_ID,
      )
      expect(restoredSource.collectBatch).not.toHaveBeenCalled()
      expect(restored.wrapper.text()).toContain('采集完成')
      expect(
        window.localStorage.getItem(
          'control-center.product-data.active-collection-batch.v1.synthetic:team.7d',
        ),
      ).toBeNull()
    } finally {
      restored.dispose()
    }
  })

  it('defaults a filtered view to that shop without losing multi-shop support', async () => {
    const dataSource = source()
    const { wrapper, dispose } = render(dataSource, { shopId: 'shop-2' })
    try {
      await openAndSubmit(wrapper)
      expect(dataSource.collectBatch).toHaveBeenCalledWith(
        expect.objectContaining({ shopIds: ['shop-2'] }),
      )
    } finally {
      dispose()
    }
  })

  it('does not submit more than the finite one-hundred-shop batch boundary', async () => {
    const dataSource = source()
    vi.mocked(dataSource.collectionShops!).mockResolvedValue(
      Array.from({ length: 101 }, (_, index) => ({
        shopId: `shop-${index + 1}`,
        shopName: `店铺 ${index + 1}`,
      })),
    )
    const { wrapper, dispose } = render(dataSource)
    try {
      wrapper.findComponent(AppButton).vm.$emit('click')
      await flushPromises()
      expect(wrapper.text()).toContain('已选择 101 家')
      expect(
        wrapper.get('[data-testid="confirm"]').attributes('disabled'),
      ).toBeDefined()
      await wrapper.get('[data-testid="confirm"]').trigger('click')
      expect(dataSource.collectBatch).not.toHaveBeenCalled()
    } finally {
      dispose()
    }
  })

  it('shows independent per-shop success and failure instead of all-or-nothing', async () => {
    const dataSource = source()
    vi.mocked(dataSource.collectionBatch!).mockResolvedValue(
      batch(['succeeded', 'failed']),
    )
    const { wrapper, queryClient, dispose } = render(dataSource)
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    try {
      await openAndSubmit(wrapper)
      expect(wrapper.text()).toContain('部分完成')
      expect(wrapper.text()).toContain('成功 1')
      expect(wrapper.text()).toContain('失败 1')
      expect(wrapper.text()).toContain('失败 · 平台请求超时')
      expect(invalidate).toHaveBeenCalledTimes(1)
    } finally {
      dispose()
    }
  })

  it('guards same-frame double submit and reuses the key after an unconfirmed POST', async () => {
    const dataSource = source()
    let reject!: (error: Error) => void
    vi.mocked(dataSource.collectBatch!).mockImplementationOnce(
      () =>
        new Promise((_, failure) => {
          reject = failure
        }),
    )
    const { wrapper, dispose } = render(dataSource)
    try {
      wrapper.findComponent(AppButton).vm.$emit('click')
      await flushPromises()
      const confirm = wrapper.get('[data-testid="confirm"]')
      await confirm.trigger('click')
      await confirm.trigger('click')
      expect(dataSource.collectBatch).toHaveBeenCalledTimes(1)
      const first = vi.mocked(dataSource.collectBatch!).mock.calls[0]![0]
      reject(new Error('synthetic submission not confirmed'))
      await flushPromises()
      expect(wrapper.text()).toContain('提交未确认')
      await confirm.trigger('click')
      await flushPromises()
      expect(vi.mocked(dataSource.collectBatch!).mock.calls[1]![0]).toEqual(
        first,
      )
    } finally {
      dispose()
    }
  })

  it('retries only the batch GET after a progress read failure', async () => {
    const dataSource = source()
    vi.mocked(dataSource.collectionBatch!)
      .mockRejectedValueOnce(new Error('synthetic receipt unavailable'))
      .mockResolvedValueOnce(batch(['succeeded', 'succeeded']))
    const { wrapper, dispose } = render(dataSource)
    try {
      await openAndSubmit(wrapper)
      expect(wrapper.text()).toContain('回执读取未完成')
      expect(wrapper.text()).toContain('重新读取进度')
      wrapper.findComponent(AppButton).vm.$emit('click')
      await flushPromises()
      expect(dataSource.collectionBatch).toHaveBeenCalledTimes(2)
      expect(dataSource.collectBatch).toHaveBeenCalledTimes(1)
      expect(wrapper.text()).toContain('采集完成')
    } finally {
      dispose()
    }
  })

  it('never submits when disabled and ignores a late result after context changes', async () => {
    const disabledSource = source()
    const disabled = render(disabledSource, { enabled: false })
    try {
      disabled.wrapper.findComponent(AppButton).vm.$emit('click')
      await flushPromises()
      expect(disabled.wrapper.find('[data-testid="dialog"]').exists()).toBe(
        false,
      )
      expect(disabledSource.collectBatch).not.toHaveBeenCalled()
    } finally {
      disabled.dispose()
    }

    const dataSource = source()
    let resolve!: (value: ProductDataCollectionBatch) => void
    vi.mocked(dataSource.collectBatch!).mockImplementationOnce(
      () => new Promise((success) => (resolve = success)),
    )
    const current = render(dataSource)
    try {
      current.wrapper.findComponent(AppButton).vm.$emit('click')
      await flushPromises()
      await current.wrapper.get('[data-testid="confirm"]').trigger('click')
      await current.wrapper.setProps({ contextKey: 'other:team' })
      resolve(batch(['succeeded', 'succeeded']))
      await flushPromises()
      expect(current.wrapper.text()).not.toContain('采集完成')
      expect(dataSource.collectionBatch).not.toHaveBeenCalled()
    } finally {
      current.dispose()
    }
  })
})
