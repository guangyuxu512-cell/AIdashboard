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
  { id: 'group-benefit', name: '福利品', count: 0 },
  { id: 'group-test', name: '测试款', count: 0 },
  { id: 'group-weekly', name: '本周上架', count: 0 },
]

const categories = [
  '厨房用品 → 厨房小工具 → 滤油壶／储油罐',
  '家居日用 → 居家布艺 → 防尘罩／空调罩／床头罩',
  '女装 → 女士上装 → 针织衫',
  '智能家居 → 智能安防 → 智能门锁',
]

const products: LibraryProduct[] = Array.from({ length: 36 }, (_, index) => {
  const productId = `${3832497447662387000n + BigInt(index)}`
  const group = index % 5 === 0 ? undefined : groups[index % 3]
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
    previewMainImageUrls: [
      main,
      images[(index + 1) % images.length]!,
      images[(index + 2) % images.length]!,
    ],
    detailImageUrls: [main, images[(index + 1) % images.length]!],
    specDimensions: [
      { id: 'color', name: '颜色' },
      { id: 'model', name: '规格' },
    ],
    skus: [
      {
        draftKey: `source:${productId}-sku-a`,
        sourceSkuId: `${productId}-sku-a`,
        name: '默认款',
        currentPrice:
          index % 9 === 0 ? null : `${(19.9 + index * 2.35).toFixed(2)}`,
        stockLabel: index % 4 === 0 ? null : '平台展示：有货',
        imageUrl: main,
        specValues: { color: '本色', model: '标准款' },
      },
      {
        draftKey: `source:${productId}-sku-b`,
        sourceSkuId: `${productId}-sku-b`,
        name: '升级款',
        currentPrice: `${(29.9 + index * 2.35).toFixed(2)}`,
        stockLabel: '平台展示：库存紧张',
        imageUrl: images[(index + 1) % images.length]!,
        specValues: { color: '升级色', model: '升级款' },
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
    mockEditedAt: null,
  }
})

// Keeps the collected Mock source intact while the working list stores edits.
const originalProducts = structuredClone(products)

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
    capabilities: {
      platformFilter: true,
      categoryFilter: true,
      edit: true,
      createGroup: true,
      moveGroup: true,
      remove: true,
      recollect: true,
      import: true,
      export: true,
      batchExport: true,
    },
    async groups() {
      refreshCounts()
      return structuredClone(groups)
    },
    async list(query: ProductLibraryQuery): Promise<ProductLibraryPage> {
      const keyword = query.keyword.trim().toLocaleLowerCase()
      const view = query.view ?? 'all'
      const filtered = products.filter(
        (product) =>
          (view === 'all' ||
            (view === 'ungrouped'
              ? product.groupId === null
              : product.groupId !== null)) &&
          (!query.platform || product.platform === query.platform) &&
          (!query.groupId || product.groupId === query.groupId) &&
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
    async saveEdit(id, draft) {
      const product = products.find((item) => item.id === id)
      if (!product) throw new Error('演示商品不存在')
      const dimensions = new Map(
        draft.specDimensions.map((dimension) => [dimension.id, dimension]),
      )
      if (
        dimensions.size !== product.specDimensions.length ||
        product.specDimensions.some(
          (dimension) => !dimensions.has(dimension.id),
        )
      )
        throw new Error('规格维度与采集资料不一致')
      const draftSkus = new Map(
        draft.skus.map((sku) => [sku.draftKey, sku] as const),
      )
      if (draftSkus.size !== draft.skus.length)
        throw new Error('SKU 草稿标识不能重复')
      const sourceSkuIds = draft.skus
        .map((sku) => sku.sourceSkuId)
        .filter((id): id is string => Boolean(id))
      if (new Set(sourceSkuIds).size !== sourceSkuIds.length)
        throw new Error('来源 SKU ID 不能重复')
      const existingSkus = new Map(
        product.skus.map((sku) => [sku.draftKey, sku] as const),
      )
      for (const draftSku of draft.skus) {
        const existing = existingSkus.get(draftSku.draftKey)
        if (existing && existing.sourceSkuId !== draftSku.sourceSkuId)
          throw new Error('来源 SKU ID 只读，不能修改')
        if (!existing && draftSku.sourceSkuId !== null)
          throw new Error('新增 SKU 不能伪造平台来源 ID')
      }

      product.title = draft.title.trim()
      product.attributes = draft.attributes.map((attribute) => ({
        name: attribute.name.trim(),
        value: attribute.value.trim(),
      }))
      product.specDimensions = product.specDimensions.map((dimension) => ({
        id: dimension.id,
        name: dimensions.get(dimension.id)!.name.trim(),
      }))
      product.skus = draft.skus.map((edited) => {
        const existing = existingSkus.get(edited.draftKey)
        return {
          draftKey: edited.draftKey,
          sourceSkuId: edited.sourceSkuId,
          name: edited.name.trim(),
          currentPrice:
            edited.currentPrice === null ? null : edited.currentPrice.trim(),
          stockLabel: existing?.stockLabel ?? null,
          imageUrl: edited.imageUrl,
          specValues: Object.fromEntries(
            product.specDimensions.map((dimension) => [
              dimension.id,
              edited.specValues[dimension.id]?.trim() ?? '',
            ]),
          ),
        }
      })
      product.currentPrice = product.skus[0]?.currentPrice ?? null
      product.mockEditedAt = new Date().toISOString()
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
    async exportSingle() {
      throw new Error('演示模式仅核对导出入口与文件清单')
    },
  }
}

export function resetProductLibraryMockStore(): void {
  products.splice(0, products.length, ...structuredClone(originalProducts))
  refreshCounts()
}
