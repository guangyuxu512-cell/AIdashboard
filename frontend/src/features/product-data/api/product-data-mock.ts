import dayjs from 'dayjs'
import { SHOP_LIST_FIXTURE } from '@/entities/shop/fixtures/shop-list.fixture'
import { productGroupNameSchema } from '../model/query'
import {
  PRODUCT_METRICS,
  type ProductColumnId,
  type ProductDataQuery,
  type ProductDataRow,
  type ProductDataSource,
  type ProductGroup,
  type ProductMetricId,
} from '../model/types'

const photos = Object.values(
  import.meta.glob('../../product-selection/fixtures/photos/*.webp', {
    eager: true,
    query: '?url',
    import: 'default',
  }),
) as string[]
export type ProductMockOperation =
  'list' | 'groups' | 'saveGroup' | 'deleteGroup' | 'assignGroup'

// Synthetic UI records; neither response sample contents nor platform facts.
export function createMockProductDataSource(
  options: { failOnce?: ProductMockOperation } = {},
): ProductDataSource {
  const shops = SHOP_LIST_FIXTURE.filter(
    (shop) => shop.enabled && shop.platform === 'douyin',
  ).slice(0, 2)
  const retrievedAt = dayjs().toISOString()
  const products = Array.from({ length: 31 }, (_, index) => {
    const shop = shops[index < 16 ? 0 : 1] ?? shops[0]!
    return {
      id: 'product-data-demo-' + index,
      shopId: shop.shopId,
      shopName: shop.shopName,
      productId: '900000000000000' + String(index + 1).padStart(4, '0'),
      title:
        index === 0
          ? '演示商品 1 · 轻盈日常随行杯 超长标题用于完整信息与省略展示'
          : '演示商品 ' + (index + 1),
      imageUrl: photos[index % photos.length] ?? null,
      groupId: null as string | null,
      selling: index % 5 === 0 ? ('off-sale' as const) : ('on-sale' as const),
      carrier: (['card', 'video', 'live'] as const)[index % 3]!,
      index,
    }
  })
  const groups: Array<{ id: string; shopId: string; name: string }> = []
  let sequence = 0
  let failure = options.failOnce
  function maybeFail(operation: ProductMockOperation) {
    if (failure !== operation) return
    failure = undefined
    throw new Error('演示操作失败，请重试')
  }
  function knownShop(shopId: string) {
    if (!shops.some((shop) => shop.shopId === shopId))
      throw new Error('请选择有商品数据的演示抖店')
  }
  function readGroup(id: string, shopId: string) {
    const group = groups.find(
      (item) => item.id === id && item.shopId === shopId,
    )
    if (!group) throw new Error('分组不属于当前店铺')
    return group
  }
  function summary(group: (typeof groups)[number]): ProductGroup {
    return {
      ...group,
      productCount: products.filter(
        (row) => row.shopId === group.shopId && row.groupId === group.id,
      ).length,
    }
  }
  function buildRow(
    product: (typeof products)[number],
    query: ProductDataQuery,
  ): ProductDataRow {
    const days =
      dayjs(query.period.endDate).diff(dayjs(query.period.startDate), 'day') + 1
    const index = product.index
    const exposure = index === 1 ? 0 : (index + 1) * 1500 * days
    const click = index === 1 ? 0 : (index + 1) * 91 * days
    const payVisitors = index === 1 ? 0 : (index + 1) * 3 * days
    const orders = index === 1 ? 0 : payVisitors + (index % 3) * days
    const values: Record<ProductMetricId, number> = {
      product_show_ucnt: exposure,
      product_click_ucnt: click,
      product_click_pay_ucnt_ratio: click ? payVisitors / click : 0,
      pay_cnt: orders,
      receive_amt: orders * 29.9,
      pay_amt: orders * 31.9,
      pay_ucnt: payVisitors,
      product_click_show_ucnt_ratio: exposure ? click / exposure : 0,
      refund_amt: (index % 3) * 12.5 * days,
      refund_cnt: (index % 3) * days,
      stock_cnt: 50 + index * 9,
    }
    const metrics = Object.fromEntries(
      PRODUCT_METRICS.map((metric) => [
        metric.id,
        {
          state: 'available',
          value: String(values[metric.id]),
          unit: metric.format === 'amount' ? 'yuan' : metric.format,
        },
      ]),
    ) as ProductDataRow['metrics']
    if (index === 2)
      metrics.product_show_ucnt = {
        state: 'missing',
        value: null,
        unit: 'count',
      }
    if (index === 3)
      metrics.receive_amt = { state: 'null', value: null, unit: 'yuan' }
    if (index === 4)
      metrics.product_click_pay_ucnt_ratio = {
        state: 'invalid',
        value: null,
        unit: 'ratio',
      }
    return {
      ...product,
      metrics,
      groupName:
        groups.find((group) => group.id === product.groupId)?.name ?? null,
      period: { ...query.period },
      retrievedAt,
    }
  }
  function sortValue(
    row: ProductDataRow,
    field: ProductColumnId,
  ): string | number | null {
    if (field === 'shop') return row.shopName
    if (field === 'group') return row.groupName
    if (field === 'selling') return row.selling
    if (field === 'carrier') return row.carrier
    if (field === 'updatedAt') return row.retrievedAt
    const metric = row.metrics[field]
    return metric.state === 'available' && metric.value !== null
      ? Number(metric.value)
      : null
  }
  return {
    mode: 'mock',
    available: true,
    async list(query) {
      maybeFail('list')
      const { filters, period, sort } = query
      if (dayjs(period.endDate).isBefore(dayjs(period.startDate)))
        throw new Error('统计日期范围无效')
      const rows = products
        .map((product) => buildRow(product, query))
        .filter((row) => {
          const exposure = row.metrics.product_show_ucnt,
            orders = row.metrics.pay_cnt
          return (
            (!filters.shopId || row.shopId === filters.shopId) &&
            (!filters.productId.trim() ||
              row.productId.includes(filters.productId.trim())) &&
            (!filters.productName.trim() ||
              row.title
                .toLocaleLowerCase()
                .includes(filters.productName.trim().toLocaleLowerCase())) &&
            (!filters.groupId ||
              (filters.groupId === 'ungrouped'
                ? row.groupId === null
                : row.groupId === filters.groupId)) &&
            (!filters.selling || row.selling === filters.selling) &&
            (!filters.carrier || row.carrier === filters.carrier) &&
            (filters.minExposure === null ||
              (exposure.state === 'available' &&
                Number(exposure.value) >= filters.minExposure)) &&
            (filters.minOrders === null ||
              (orders.state === 'available' &&
                Number(orders.value) >= filters.minOrders))
          )
        })
      if (sort)
        rows.sort((left, right) => {
          const a = sortValue(left, sort.field),
            b = sortValue(right, sort.field)
          if (a === null || b === null)
            return a === b
              ? left.id.localeCompare(right.id)
              : a === null
                ? 1
                : -1
          const difference =
            typeof a === 'number' && typeof b === 'number'
              ? a - b
              : String(a).localeCompare(String(b), 'zh-CN')
          return (
            (sort.direction === 'asc' ? difference : -difference) ||
            left.id.localeCompare(right.id)
          )
        })
      const page = Math.max(
        1,
        Math.min(
          query.page,
          Math.max(1, Math.ceil(rows.length / query.pageSize)),
        ),
      )
      return {
        items: rows.slice((page - 1) * query.pageSize, page * query.pageSize),
        total: rows.length,
        page,
        pageSize: query.pageSize,
      }
    },
    async groups(shopId) {
      maybeFail('groups')
      knownShop(shopId)
      return groups.filter((group) => group.shopId === shopId).map(summary)
    },
    async saveGroup(shopId, input) {
      maybeFail('saveGroup')
      knownShop(shopId)
      const name = productGroupNameSchema.parse(input.name)
      if (
        groups.some(
          (group) =>
            group.shopId === shopId &&
            group.name === name &&
            group.id !== input.id,
        )
      )
        throw new Error('当前店铺已有同名分组')
      if (input.id) {
        const group = readGroup(input.id, shopId)
        group.name = name
        return summary(group)
      }
      const group = { id: 'product-group-demo-' + ++sequence, shopId, name }
      groups.push(group)
      return summary(group)
    },
    async deleteGroup(shopId, groupId) {
      maybeFail('deleteGroup')
      knownShop(shopId)
      readGroup(groupId, shopId)
      for (const row of products)
        if (row.shopId === shopId && row.groupId === groupId) row.groupId = null
      groups.splice(
        groups.findIndex(
          (group) => group.id === groupId && group.shopId === shopId,
        ),
        1,
      )
    },
    async assignGroup(shopId, productIds, groupId) {
      maybeFail('assignGroup')
      knownShop(shopId)
      if (!productIds.length) throw new Error('请先勾选商品')
      if (groupId !== null) readGroup(groupId, shopId)
      const targets = productIds.map((id) =>
        products.find((row) => row.id === id),
      )
      if (targets.some((row) => !row || row.shopId !== shopId))
        throw new Error('只能设置同一店铺的商品分组')
      for (const row of targets) row!.groupId = groupId
    },
  }
}
