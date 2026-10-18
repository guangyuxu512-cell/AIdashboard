import { flushPromises, mount } from '@vue/test-utils'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { defineComponent, h, ref } from 'vue'
import { NMessageProvider } from 'naive-ui'
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import { AppButton, AppDialog, AppInput, AppSelect } from '@/shared/ui'
import {
  ManagementListSection,
  PaginationBar,
  TableToolbar,
} from '@/shared/components'
import { createMockProductDataSource } from '../api/product-data-mock'
import {
  createUnavailableProductDataSource,
  PRODUCT_DATA_UNAVAILABLE,
} from '../api/product-data-source'
import { readProductColumns } from '../model/column-preferences'
import { emptyProductFilters } from '../model/query'
import type { ProductDataSource } from '../model/types'
import ProductDataView from './ProductDataView.vue'
import ProductDataFilterBar from './ProductDataFilterBar.vue'
import ProductDataTable from './ProductDataTable.vue'
import ProductDataDetailDrawer from './ProductDataDetailDrawer.vue'
import ProductGroupManagerDialog from './ProductGroupManagerDialog.vue'
import ProductBatchGroupDialog from './ProductBatchGroupDialog.vue'
import ProductFieldConfigDialog from './ProductFieldConfigDialog.vue'

let previousCompactHeight = ''
beforeAll(() => {
  previousCompactHeight = document.documentElement.style.getPropertyValue(
    '--list-compact-control-height',
  )
  document.documentElement.style.setProperty(
    '--list-compact-control-height',
    '28px',
  )
})
afterAll(() => {
  if (previousCompactHeight)
    document.documentElement.style.setProperty(
      '--list-compact-control-height',
      previousCompactHeight,
    )
  else
    document.documentElement.style.removeProperty(
      '--list-compact-control-height',
    )
})

const DialogStub = defineComponent({
  props: ['show', 'title', 'positiveDisabled'],
  emits: ['confirm', 'update:show'],
  template:
    '<section v-if="show"><slot /><slot name="footer-start" /></section>',
})
const ShopStub = defineComponent({
  props: ['modelValue'],
  emits: ['update:modelValue'],
  template: '<div />',
})
function render(
  component: Parameters<typeof h>[0],
  props: Record<string, unknown>,
  stubs: Record<string, unknown> = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  const wrapper = mount(
    defineComponent({
      setup: () => () =>
        h(NMessageProvider, {}, { default: () => h(component, props) }),
    }),
    {
      global: {
        plugins: [[VueQueryPlugin, { queryClient }]],
        stubs: { AppDialog: DialogStub, ShopSelector: ShopStub, ...stubs },
      },
    },
  )
  return {
    wrapper,
    queryClient,
    dispose: () => {
      wrapper.unmount()
      queryClient.clear()
    },
  }
}
function button(wrapper: ReturnType<typeof mount>, text: string) {
  return wrapper
    .findAllComponents(AppButton)
    .find((item) => item.text() === text)!
}
describe('product data view and recovery', () => {
  it('validates ranges before querying, applies immutable drafts across all data, and keeps hidden-field filters on page one', async () => {
    const source = createMockProductDataSource(),
      list = vi.spyOn(source, 'list')
    const { wrapper, dispose } = render(
      ProductDataView,
      { source, contextKey: 'ranges:team', userId: 'ranges' },
      {
        ProductDataTable: true,
        ProductFieldConfigDialog: true,
        ProductGroupManagerDialog: true,
        ProductBatchGroupDialog: true,
        ProductDataDetailDrawer: true,
      },
    )
    try {
      await flushPromises()
      const filter = wrapper.findComponent(ProductDataFilterBar),
        table = wrapper.findComponent(ProductDataTable)
      wrapper.findComponent(PaginationBar).vm.$emit('update:page', 2)
      await flushPromises()
      table.vm.$emit('update:checked', ['product-data-demo-20'])
      const previousCalls = list.mock.calls.length
      let filters = filter.props('modelValue')
      filter.vm.$emit('update:modelValue', {
        ...filters,
        metricRanges: {
          ...filters.metricRanges,
          exposureCount: { choice: 'custom', min: -1, max: null },
        },
      })
      await flushPromises()
      filter.vm.$emit('query')
      await flushPromises()
      expect(list).toHaveBeenCalledTimes(previousCalls)
      expect(filter.props('rangeErrors')?.exposureCount).toContain('负数')
      expect(wrapper.findComponent(PaginationBar).props('page')).toBe(2)
      filters = filter.props('modelValue')
      filter.vm.$emit('update:modelValue', {
        ...filters,
        metricRanges: {
          ...filters.metricRanges,
          exposureCount: { choice: 'custom', min: 0, max: 1000 },
        },
      })
      await flushPromises()
      filter.vm.$emit('query')
      await flushPromises()
      expect(wrapper.findComponent(PaginationBar).props('page')).toBe(1)
      expect(table.props('checked')).toEqual([])
      expect(
        table
          .props('rows')
          .some((row: { id: string }) => row.id === 'product-data-demo-27'),
      ).toBe(true)
      const applied = list.mock.calls.at(-1)![0]
      wrapper
        .findComponent(ProductFieldConfigDialog)
        .vm.$emit('saved', ['shop'])
      await flushPromises()
      expect(filter.props('modelValue').metricRanges.exposureCount).toEqual({
        choice: 'custom',
        min: 0,
        max: 1000,
      })
      filters = filter.props('modelValue')
      filter.vm.$emit('update:modelValue', {
        ...filters,
        metricRanges: {
          ...filters.metricRanges,
          exposureCount: { choice: 'custom', min: 10000, max: null },
        },
      })
      await flushPromises()
      expect(applied.filters.metricRanges.exposureCount.min).toBe(0)
      filter.vm.$emit('reset')
      await flushPromises()
      expect(table.props('rows')).toHaveLength(20)
      expect(wrapper.findComponent(PaginationBar).props('pageSize')).toBe(20)
      expect(
        Object.values(filter.props('modelValue').metricRanges).every(
          (range) => (range as { choice: string }).choice === 'unlimited',
        ),
      ).toBe(true)
    } finally {
      dispose()
    }
  })
  it('opts only the list into compact density and declares every overlay outside its boundary', async () => {
    const { wrapper, dispose } = render(
      ProductDataView,
      {
        source: createMockProductDataSource(),
        contextKey: 'density:team',
        userId: 'density',
      },
      {
        ProductDataTable: true,
        ProductFieldConfigDialog: true,
        ProductGroupManagerDialog: true,
        ProductBatchGroupDialog: true,
        ProductDataDetailDrawer: true,
      },
    )
    await flushPromises()
    expect(wrapper.findComponent(ManagementListSection).props('density')).toBe(
      'compact',
    )
    expect(wrapper.findComponent(TableToolbar).props('density')).toBe('compact')
    expect(wrapper.findComponent(PaginationBar).props('density')).toBe(
      'compact',
    )
    const filter = wrapper.findComponent(ProductDataFilterBar)
    filter.vm.$emit('update:modelValue', {
      ...filter.props('modelValue'),
      shopId: 'shop-fixture-001',
    })
    await flushPromises()
    wrapper
      .findComponent(ProductDataTable)
      .vm.$emit('update:checked', ['product-data-demo-0'])
    await flushPromises()
    const list = wrapper.find('.management-list-section').element
    for (const overlay of [
      ProductFieldConfigDialog,
      ProductGroupManagerDialog,
      ProductBatchGroupDialog,
      ProductDataDetailDrawer,
    ]) {
      const component = wrapper.findComponent(overlay)
      expect(component.exists()).toBe(true)
      expect(list.contains(component.element)).toBe(false)
    }
    dispose()
  })
  it('starts at twenty per page, retains explicit page-size changes and resets page and selection without storage writes', async () => {
    const source = createMockProductDataSource()
    const list = vi.spyOn(source, 'list')
    const storage = vi.spyOn(Storage.prototype, 'setItem')
    const { wrapper, dispose } = render(
      ProductDataView,
      { source, contextKey: 'paging:team', userId: 'paging' },
      {
        ProductDataTable: true,
        ProductFieldConfigDialog: true,
        ProductGroupManagerDialog: true,
        ProductBatchGroupDialog: true,
        ProductDataDetailDrawer: true,
      },
    )
    try {
      await flushPromises()
      const pagination = () => wrapper.findComponent(PaginationBar)
      const table = wrapper.findComponent(ProductDataTable),
        filter = wrapper.findComponent(ProductDataFilterBar)
      expect(list).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 1, pageSize: 20 }),
      )
      expect(pagination().props('pageSize')).toBe(20)
      expect(table.props('rows')).toHaveLength(20)
      pagination().vm.$emit('update:pageSize', 10)
      await flushPromises()
      expect(pagination().props('pageSize')).toBe(10)
      expect(table.props('rows')).toHaveLength(10)
      pagination().vm.$emit('update:page', 2)
      await flushPromises()
      expect(pagination().props('page')).toBe(2)
      table.vm.$emit('update:checked', [table.props('rows')[0].id])
      await flushPromises()
      pagination().vm.$emit('update:pageSize', 50)
      await flushPromises()
      expect(pagination().props('page')).toBe(1)
      expect(pagination().props('pageSize')).toBe(50)
      expect(table.props('checked')).toEqual([])
      expect(table.props('rows')).toHaveLength(31)
      filter.vm.$emit('reset')
      await flushPromises()
      table.vm.$emit('update:sort', { field: 'receive_amt', direction: 'desc' })
      await flushPromises()
      expect(list).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 1, pageSize: 50 }),
      )
      expect(pagination().props('pageSize')).toBe(50)
      expect(storage).not.toHaveBeenCalled()
    } finally {
      dispose()
      storage.mockRestore()
    }
  })
  it('keeps filters mounted during loading and error, retries and distinguishes empty success', async () => {
    const source = createMockProductDataSource()
    const original = source.list
    let resolve!: (
      value: Awaited<ReturnType<ProductDataSource['list']>>,
    ) => void
    source.list = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise((done) => {
            resolve = done
          }),
      )
      .mockImplementation(original)
    const { wrapper, dispose } = render(
      ProductDataView,
      { source, contextKey: 'a:team', userId: 'a' },
      {
        ProductDataTable: true,
        ProductFieldConfigDialog: true,
        ProductGroupManagerDialog: true,
        ProductBatchGroupDialog: true,
        ProductDataDetailDrawer: true,
      },
    )
    await flushPromises()
    expect(wrapper.findComponent(ProductDataFilterBar).exists()).toBe(true)
    expect(wrapper.findComponent(ProductDataTable).props('loading')).toBe(true)
    resolve({ items: [], total: 0, page: 1, pageSize: 10 })
    await flushPromises()
    expect(wrapper.findComponent(ProductDataTable).props('rows')).toEqual([])
    vi.mocked(source.list).mockRejectedValueOnce(new Error('读取失败测试'))
    wrapper.findComponent(ProductDataFilterBar).vm.$emit('query')
    await flushPromises()
    expect(wrapper.findComponent(ProductDataTable).props('error')).toBe(
      '读取失败测试',
    )
    wrapper.findComponent(ProductDataTable).vm.$emit('retry')
    await flushPromises()
    expect(wrapper.findComponent(ProductDataTable).props('rows')).toHaveLength(
      20,
    )
    expect(wrapper.findComponent(ProductDataTable).props('error')).toBeNull()
    dispose()
  })
  it('applies draft filters on query, resets page and selection on sort/shop changes, and guards mixed shops', async () => {
    const source = createMockProductDataSource()
    const { wrapper, dispose } = render(
      ProductDataView,
      { source, contextKey: 'a:team', userId: 'a' },
      {
        ProductDataTable: true,
        ProductFieldConfigDialog: true,
        ProductGroupManagerDialog: true,
        ProductBatchGroupDialog: true,
        ProductDataDetailDrawer: true,
      },
    )
    await flushPromises()
    const filter = wrapper.findComponent(ProductDataFilterBar),
      table = wrapper.findComponent(ProductDataTable)
    filter.vm.$emit('update:modelValue', {
      ...filter.props('modelValue'),
      productName: '演示商品 31',
    })
    await flushPromises()
    expect(table.props('rows')).toHaveLength(20)
    filter.vm.$emit('query')
    await flushPromises()
    expect(table.props('rows')).toHaveLength(1)
    filter.vm.$emit('reset')
    await flushPromises()
    table.vm.$emit('update:checked', ['product-data-demo-0'])
    await flushPromises()
    expect(button(wrapper, '批量设置分组').props('disabled')).toBe(false)
    wrapper.findComponent(PaginationBar).vm.$emit('update:pageSize', 100)
    await flushPromises()
    table.vm.$emit('update:checked', [
      'product-data-demo-0',
      'product-data-demo-30',
    ])
    await flushPromises()
    expect(button(wrapper, '批量设置分组').props('disabled')).toBe(true)
    table.vm.$emit('update:sort', { field: 'receive_amt', direction: 'desc' })
    await flushPromises()
    expect(table.props('checked')).toEqual([])
    expect(table.props('rows')[0].id).toBe('product-data-demo-30')
    filter.vm.$emit('update:modelValue', {
      ...filter.props('modelValue'),
      shopId: 'shop-fixture-003',
      groupId: 'old-shop-group',
    })
    await flushPromises()
    expect(filter.props('modelValue').groupId).toBeNull()
    dispose()
  })
  it('Real exposes unavailable read and disables writes without showing demo rows', async () => {
    const { wrapper, dispose } = render(
      ProductDataView,
      {
        source: createUnavailableProductDataSource(),
        contextKey: 'real:team',
        userId: 'real',
      },
      {
        ProductDataTable: true,
        ProductFieldConfigDialog: true,
        ProductGroupManagerDialog: true,
        ProductBatchGroupDialog: true,
        ProductDataDetailDrawer: true,
      },
    )
    await flushPromises()
    expect(wrapper.findComponent(ProductDataTable).props('error')).toBe(
      PRODUCT_DATA_UNAVAILABLE,
    )
    expect(wrapper.findComponent(ProductDataTable).props('rows')).toEqual([])
    expect(button(wrapper, '分组管理').props('disabled')).toBe(true)
    expect(button(wrapper, '批量设置分组').props('disabled')).toBe(true)
    expect(wrapper.text()).not.toContain('演示数据')
    expect(wrapper.findComponent(PaginationBar).exists()).toBe(false)
    dispose()
  })
  it('surfaces group read failure and recovers rather than presenting an empty group list', async () => {
    const source = createMockProductDataSource({ failOnce: 'groups' })
    const { wrapper, dispose } = render(
      ProductDataView,
      { source, contextKey: 'groups:team', userId: 'groups' },
      {
        ProductDataTable: true,
        ProductFieldConfigDialog: true,
        ProductGroupManagerDialog: true,
        ProductBatchGroupDialog: true,
        ProductDataDetailDrawer: true,
      },
    )
    await flushPromises()
    const filter = wrapper.findComponent(ProductDataFilterBar)
    filter.vm.$emit('update:modelValue', {
      ...filter.props('modelValue'),
      shopId: 'shop-fixture-001',
    })
    await flushPromises()
    expect(filter.props('groupsError')).toBe(true)
    expect(wrapper.text()).toContain('分组读取失败')
    filter.vm.$emit('retryGroups')
    await flushPromises()
    expect(filter.props('groupsError')).toBe(false)
    dispose()
  })
  it('does not let a late prior-context response replace a remounted context', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    const sourceA = createMockProductDataSource(),
      sourceB = createMockProductDataSource()
    let resolve!: (
      value: Awaited<ReturnType<ProductDataSource['list']>>,
    ) => void
    sourceA.list = vi.fn(
      () =>
        new Promise<Awaited<ReturnType<ProductDataSource['list']>>>((done) => {
          resolve = done
        }),
    )
    const context = ref('a')
    const wrapper = mount(
      defineComponent({
        setup: () => () =>
          h(
            NMessageProvider,
            {},
            {
              default: () =>
                h(ProductDataView, {
                  key: context.value,
                  source: context.value === 'a' ? sourceA : sourceB,
                  contextKey: context.value,
                  userId: context.value,
                }),
            },
          ),
      }),
      {
        global: {
          plugins: [[VueQueryPlugin, { queryClient }]],
          stubs: {
            ShopSelector: ShopStub,
            ProductDataTable: true,
            ProductFieldConfigDialog: true,
            ProductGroupManagerDialog: true,
            ProductBatchGroupDialog: true,
            ProductDataDetailDrawer: true,
          },
        },
      },
    )
    await flushPromises()
    context.value = 'b'
    await flushPromises()
    resolve({ items: [], total: 0, page: 1, pageSize: 10 })
    await flushPromises()
    expect(wrapper.findComponent(ProductDataTable).props('rows')).toHaveLength(
      20,
    )
    expect(
      wrapper.findComponent(ProductFieldConfigDialog).props('userId'),
    ).toBe('b')
    wrapper.unmount()
    queryClient.clear()
  })
})
describe('product data edit drafts', () => {
  it('retains new-group draft after a save failure, retries and reads the created group back', async () => {
    const source = createMockProductDataSource({ failOnce: 'saveGroup' })
    const { wrapper, dispose } = render(ProductGroupManagerDialog, {
      show: true,
      source,
      shopId: 'shop-fixture-001',
      contextKey: 'a',
    })
    await flushPromises()
    wrapper.findComponent(AppInput).vm.$emit('update:modelValue', '出单款')
    await flushPromises()
    button(wrapper, '创建分组').vm.$emit('click')
    await flushPromises()
    expect(wrapper.findComponent(AppInput).props('modelValue')).toBe('出单款')
    expect(wrapper.text()).toContain('演示操作失败')
    button(wrapper, '创建分组').vm.$emit('click')
    await flushPromises()
    expect(wrapper.text()).toContain('出单款')
    expect((await source.groups('shop-fixture-001'))[0]!.name).toBe('出单款')
    dispose()
  })
  it('keeps batch target and selected products after failure and retries without cross-shop writes', async () => {
    const source = createMockProductDataSource({ failOnce: 'assignGroup' })
    const params = {
      filters: emptyProductFilters(),
      period: { startDate: '2026-10-01', endDate: '2026-10-01' },
      page: 1,
      pageSize: 10,
      sort: null,
    }
    const row = (await source.list(params)).items[0]!
    const group = await source.saveGroup(row.shopId, {
      id: null,
      name: '出单款',
    })
    const { wrapper, dispose } = render(ProductBatchGroupDialog, {
      show: true,
      source,
      shopId: row.shopId,
      rows: [row],
      contextKey: 'a',
    })
    await flushPromises()
    wrapper.findComponent(AppSelect).vm.$emit('update:modelValue', group.id)
    wrapper.findComponent(AppDialog).vm.$emit('confirm')
    await flushPromises()
    expect(wrapper.findComponent(AppSelect).props('modelValue')).toBe(group.id)
    expect(
      wrapper.findComponent(ProductBatchGroupDialog).emitted('saved'),
    ).toBeUndefined()
    wrapper.findComponent(AppDialog).vm.$emit('confirm')
    await flushPromises()
    expect(
      wrapper.findComponent(ProductBatchGroupDialog).emitted('saved'),
    ).toHaveLength(1)
    expect((await source.groups(row.shopId))[0]!.productCount).toBe(1)
    dispose()
  })
  it('keeps personal column choices after storage failure and only closes after a successful retry', async () => {
    const { wrapper, dispose } = render(ProductFieldConfigDialog, {
      show: true,
      columns: ['pay_cnt'],
      userId: 'prefs-test',
    })
    const component = wrapper.findComponent(ProductFieldConfigDialog)
    const write = vi
      .spyOn(Storage.prototype, 'setItem')
      .mockImplementationOnce(() => {
        throw new Error('quota')
      })
    wrapper.findComponent(AppDialog).vm.$emit('confirm')
    await flushPromises()
    expect(wrapper.text()).toContain('保存失败')
    expect(component.emitted('saved')).toBeUndefined()
    wrapper.findComponent(AppDialog).vm.$emit('confirm')
    await flushPromises()
    expect(component.emitted('saved')?.[0]).toEqual([['pay_cnt']])
    expect(readProductColumns('prefs-test')).toEqual(['pay_cnt'])
    write.mockRestore()
    dispose()
  })
})
