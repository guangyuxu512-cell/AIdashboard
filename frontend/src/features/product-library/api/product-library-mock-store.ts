import type {
  LibraryProduct,
  ProductGroup,
  ProductLibraryPage,
  ProductLibraryQuery,
  ProductLibraryService,
} from '../model/contracts'

function fixtureImage(label: string, background: string): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="640" viewBox="0 0 640 640"><rect width="640" height="640" rx="48" fill="${background}"/><circle cx="320" cy="265" r="138" fill="#fff" fill-opacity=".82"/><rect x="170" y="438" width="300" height="18" rx="9" fill="#fff" fill-opacity=".72"/><text x="320" y="565" text-anchor="middle" font-family="Segoe UI, sans-serif" font-size="42" fill="#fff">${label}</text></svg>`
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}

const images = [
  fixtureImage('HOME', '#2f6f45'),
  fixtureImage('STYLE', '#d52e3b'),
  fixtureImage('LIFE', '#2563eb'),
  fixtureImage('SMART', '#12a08f'),
]

let groupSequence = 4
const groups: ProductGroup[] = [
  { id: 'group-hot', name: '重点跟进', count: 0 },
  { id: 'group-review', name: '待复核', count: 0 },
  { id: 'group-ready', name: '可上架', count: 0 },
]

const categories = ['厨房用品', '家居收纳', '女装', '智能设备']

const products: LibraryProduct[] = Array.from({ length: 36 }, (_, index) => {
  const productId = `${3832497447662387000n + BigInt(index)}`
  const group = groups[index % 5 === 0 ? 1 : index % 3]
  const main = images[index % images.length]!
  return {
    id: `library-demo-${index + 1}`,
    productId,
    platform: (['douyin', 'pdd', 'taobao'] as const)[index % 3]!,
    title:
      index === 0
        ? '家用多规格不锈钢带滤网储油罐 厨房防漏油壶长标题演示'
        : `演示商品资料 ${index + 1}`,
    groupId: group?.id ?? null,
    groupName: group?.name ?? null,
    category: index % 7 === 0 ? null : categories[index % categories.length]!,
    currentPrice:
      index % 9 === 0 ? null : `${(19.9 + index * 2.35).toFixed(2)}`,
    collectedAt: `2026-10-${String(1 + (index % 19)).padStart(2, '0')}T${String(8 + (index % 10)).padStart(2, '0')}:20:00+08:00`,
    sourceUrl:
      index % 6 === 0 ? null : `https://example.invalid/product/${productId}`,
    mainImageUrl: main,
    detailImageUrls: [main, images[(index + 1) % images.length]!],
    skuImageUrls: [main, images[(index + 2) % images.length]!],
    skus: [
      {
        id: `${productId}-sku-a`,
        name: '默认款',
        currentPrice:
          index % 9 === 0 ? null : `${(19.9 + index * 2.35).toFixed(2)}`,
        stockLabel: index % 4 === 0 ? null : '平台展示：有货',
        imageUrl: main,
      },
      {
        id: `${productId}-sku-b`,
        name: '升级款',
        currentPrice: `${(29.9 + index * 2.35).toFixed(2)}`,
        stockLabel: '平台展示：库存紧张',
        imageUrl: images[(index + 1) % images.length]!,
      },
    ],
    attributes: [
      { name: '材质', value: index % 2 ? '棉' : '不锈钢' },
      { name: '产地', value: '中国' },
      { name: '货号', value: `DEMO-${String(index + 1).padStart(4, '0')}` },
    ],
    packageFiles: [
      { name: `${productId}.txt`, kind: 'txt' },
      { name: `${productId}.origin.txt`, kind: 'origin-txt' },
      { name: 'images/main.webp', kind: 'image' },
    ],
    history: [
      {
        id: `history-${index}-1`,
        collectedAt: `2026-10-${String(1 + (index % 19)).padStart(2, '0')}T10:00:00+08:00`,
        state: 'completed',
        summary: '演示资料已接收并整理',
      },
    ],
  }
})

function refreshCounts() {
  for (const group of groups)
    group.count = products.filter(
      (product) => product.groupId === group.id,
    ).length
}
refreshCounts()

export function createProductLibraryMockService(): ProductLibraryService {
  return {
    available: true,
    mode: 'mock',
    async groups() {
      refreshCounts()
      return structuredClone(groups)
    },
    async list(query: ProductLibraryQuery): Promise<ProductLibraryPage> {
      const keyword = query.keyword.trim().toLocaleLowerCase()
      const filtered = products.filter(
        (product) =>
          (!query.platform || product.platform === query.platform) &&
          (!query.groupId ||
            (query.groupId === 'ungrouped'
              ? product.groupId === null
              : product.groupId === query.groupId)) &&
          (!query.category || product.category === query.category) &&
          (!keyword ||
            `${product.title} ${product.productId} ${product.category ?? ''}`
              .toLocaleLowerCase()
              .includes(keyword)),
      )
      const page = Math.min(
        query.page,
        Math.max(1, Math.ceil(filtered.length / query.pageSize)),
      )
      return {
        items: structuredClone(
          filtered.slice((page - 1) * query.pageSize, page * query.pageSize),
        ),
        total: filtered.length,
        page,
        pageSize: query.pageSize,
        categories: [...categories],
      }
    },
    async detail(id) {
      const product = products.find((item) => item.id === id)
      if (!product) throw new Error('演示商品不存在')
      return structuredClone(product)
    },
    async createGroup(name) {
      const normalized = name.trim()
      if (!normalized) throw new Error('请输入分组名称')
      if (groups.some((group) => group.name === normalized))
        throw new Error('分组名称已存在')
      const group = {
        id: `group-demo-${++groupSequence}`,
        name: normalized,
        count: 0,
      }
      groups.push(group)
      return structuredClone(group)
    },
    async moveToGroup(ids, groupId) {
      const group = groupId ? groups.find((item) => item.id === groupId) : null
      if (groupId && !group) throw new Error('演示分组不存在')
      let changed = 0
      for (const id of new Set(ids)) {
        const product = products.find((item) => item.id === id)
        if (!product) continue
        product.groupId = group?.id ?? null
        product.groupName = group?.name ?? null
        changed += 1
      }
      refreshCounts()
      return changed
    },
    async remove(ids) {
      let changed = 0
      for (const id of new Set(ids)) {
        const index = products.findIndex((item) => item.id === id)
        if (index < 0) continue
        products.splice(index, 1)
        changed += 1
      }
      refreshCounts()
      return changed
    },
    async recollect(ids) {
      const selected = products.filter((item) => ids.includes(item.id))
      const { enqueueCandidateCollectionTasks } =
        await import('@/features/product-collection/api/collection-task-mock-store')
      return enqueueCandidateCollectionTasks(
        selected.map((product) => ({
          candidateId: product.id,
          productId: product.productId,
          title: product.title,
          platform: product.platform,
        })),
      ).length
    },
  }
}

export function resetProductLibraryMockStore(): void {
  // Tests mutate only through a fresh worker in current Gate; explicit reset is
  // kept for future targeted tests without rebuilding the production service.
  refreshCounts()
}
