import { mount } from '@vue/test-utils'
import type { VNode } from 'vue'
import type { DataTableBaseColumn } from 'naive-ui'
import { describe, expect, it } from 'vitest'
import { ProductInfoCell } from '@/entities/product'
import { DataTable } from '@/shared/components'
import { createMockProductDataSource } from '../api/product-data-mock'
import { emptyProductFilters } from '../model/query'
import {
  DEFAULT_PRODUCT_COLUMNS,
  PRODUCT_COLUMNS,
  type ProductDataRow,
} from '../model/types'
import ProductDataTable from './ProductDataTable.vue'

describe('product data compact table consumer', () => {
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
    expect(table.props('scrollX')).toBe(
      44 +
        304 +
        88 +
        DEFAULT_PRODUCT_COLUMNS.reduce(
          (sum, id) =>
            sum + PRODUCT_COLUMNS.find((column) => column.id === id)!.width,
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
