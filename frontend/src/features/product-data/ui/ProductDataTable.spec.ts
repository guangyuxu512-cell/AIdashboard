import { mount } from '@vue/test-utils'
import { defineComponent, h, nextTick, reactive, type VNode } from 'vue'
import {
  NConfigProvider,
  NMessageProvider,
  type DataTableBaseColumn,
} from 'naive-ui'
import { describe, expect, it } from 'vitest'
import { ProductInfoCell } from '@/entities/product'
import { DataTable } from '@/shared/components'
import { createMockProductDataSource } from '../api/product-data-mock'
import { emptyProductFilters } from '../model/query'
import {
  DEFAULT_PRODUCT_COLUMNS,
  PRODUCT_DISPLAY_COLUMNS,
  type ProductDisplayColumnId,
  type ProductDataRow,
} from '../model/types'
import ProductDataTable from './ProductDataTable.vue'

describe('product data compact table consumer', () => {
  it('keeps fixed and configured headers only around successful empty results across state changes', async () => {
    const visibleColumns: ProductDisplayColumnId[] = [
      'clickCount',
      'shop',
      'pay_cnt',
    ]
    const state = reactive<{
      loading: boolean
      error: string | null
    }>({ loading: true, error: null })
    let retries = 0
    const Harness = defineComponent({
      setup: () => () =>
        h(
          NConfigProvider,
          { abstract: true },
          {
            default: () =>
              h(NMessageProvider, null, {
                default: () =>
                  h(ProductDataTable, {
                    rows: [],
                    visibleColumns,
                    checked: [],
                    sort: null,
                    loading: state.loading,
                    error: state.error,
                    enabled: true,
                    nativeOnly: true,
                    onRetry: () => retries++,
                  }),
              }),
          },
        ),
    })
    const wrapper = mount(Harness)
    const headerLabels = () =>
      wrapper.findAll('.n-data-table-th').map((header) => header.text().trim())
    try {
      expect(wrapper.text()).toContain('正在加载')
      expect(headerLabels()).toEqual([])
      expect(wrapper.text()).not.toContain('所选范围暂无商品数据')

      state.loading = false
      await nextTick()
      expect(headerLabels()).toEqual([
        '',
        '商品信息',
        '点击量',
        '店铺',
        '订单数',
        '操作',
      ])
      expect(wrapper.get('.n-data-table-empty').text()).toContain(
        '所选范围暂无商品数据',
      )
      expect(
        wrapper.findAll('.n-data-table-tbody .n-data-table-tr'),
      ).toHaveLength(0)

      state.error = '读取失败测试'
      await nextTick()
      expect(wrapper.text()).toContain('读取失败测试')
      expect(headerLabels()).toEqual([])
      expect(wrapper.text()).not.toContain('所选范围暂无商品数据')
      await wrapper.get('button').trigger('click')
      expect(retries).toBe(1)

      state.error = null
      await nextTick()
      expect(headerLabels()).toEqual([
        '',
        '商品信息',
        '点击量',
        '店铺',
        '订单数',
        '操作',
      ])
      expect(wrapper.get('.n-data-table-empty').text()).toContain(
        '所选范围暂无商品数据',
      )
    } finally {
      wrapper.unmount()
    }
  })
  it('renders only the approved whitelist and reuses verified sorts for both traffic aliases', async () => {
    const savedOrder = PRODUCT_DISPLAY_COLUMNS.map(({ id }) => id).reverse()
    const wrapper = mount(ProductDataTable, {
      props: {
        rows: [],
        visibleColumns: savedOrder,
        checked: [],
        sort: null,
        loading: false,
        error: null,
        enabled: true,
        nativeOnly: true,
      },
      global: { stubs: { DataTable: true } },
    })
    try {
      const columns = wrapper
        .findComponent(DataTable)
        .props('columns') as DataTableBaseColumn<ProductDataRow>[]
      expect(columns.slice(2, -1).map((column) => column.key)).toEqual(
        savedOrder,
      )
      for (const field of PRODUCT_DISPLAY_COLUMNS)
        expect(columns.find((column) => column.key === field.id)?.sorter).toBe(
          true,
        )
      expect(columns.some((column) => column.key === 'receive_amt')).toBe(false)
      expect(columns.some((column) => column.key === 'stock_cnt')).toBe(false)
      await wrapper.setProps({ enabled: false })
      const disabledColumns = wrapper
        .findComponent(DataTable)
        .props('columns') as DataTableBaseColumn<ProductDataRow>[]
      for (const field of PRODUCT_DISPLAY_COLUMNS)
        expect(
          disabledColumns.find((column) => column.key === field.id)?.sorter,
        ).toBe(false)
    } finally {
      wrapper.unmount()
    }
  })
  it('uses its own bounded product width and explicit shared compact props without changing configured field order', async () => {
    const rows = (
      await createMockProductDataSource().list({
        filters: emptyProductFilters(),
        period: { startDate: '2026-10-01', endDate: '2026-10-01' },
        page: 1,
        pageSize: 20,
        sort: null,
      })
    ).items
    const wrapper = mount(ProductDataTable, {
      props: {
        rows,
        visibleColumns: [...DEFAULT_PRODUCT_COLUMNS],
        checked: [],
        sort: null,
        loading: false,
        error: null,
        enabled: true,
      },
      global: { stubs: { DataTable: true } },
    })
    const table = wrapper.findComponent(DataTable),
      columns = table.props('columns') as DataTableBaseColumn<ProductDataRow>[],
      product = columns.find((column) => column.key === 'product')!
    expect(product).toMatchObject({
      width: 304,
      minWidth: 304,
      maxWidth: 304,
      fixed: 'left',
    })
    const cell = product.render!(rows[0]!, 0) as VNode
    expect(cell.type).toBe(ProductInfoCell)
    expect(cell.props).toMatchObject({
      density: 'compact',
      productId: rows[0]!.productId,
    })
    expect(columns.slice(2, -1).map((column) => column.key)).toEqual(
      DEFAULT_PRODUCT_COLUMNS,
    )
    for (const column of columns.slice(2, -1)) {
      const width = PRODUCT_DISPLAY_COLUMNS.find(
        (field) => field.id === column.key,
      )!.width
      expect(column).toMatchObject({ width, minWidth: width, maxWidth: width })
    }
    expect(table.props('scrollX')).toBe(
      44 +
        304 +
        88 +
        DEFAULT_PRODUCT_COLUMNS.reduce(
          (sum, id) =>
            sum +
            PRODUCT_DISPLAY_COLUMNS.find((column) => column.id === id)!.width,
          0,
        ),
    )
    expect(columns.at(-1)).toMatchObject({
      key: 'actions',
      fixed: 'right',
      width: 88,
    })
    wrapper.unmount()
  })
})
