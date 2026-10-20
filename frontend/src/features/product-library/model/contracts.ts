import type { PlatformCode } from '@/entities/platform/model/registry'

export interface ProductGroup {
  id: string
  name: string
  count: number
}

export interface ProductSku {
  id: string
  name: string
  currentPrice: string | null
  stockLabel: string | null
  imageUrl: string | null
}

export interface ProductHistory {
  id: string
  collectedAt: string
  state: 'completed' | 'partial' | 'failed'
  summary: string
}

export interface LibraryProduct {
  id: string
  productId: string
  platform: PlatformCode
  title: string
  groupId: string | null
  groupName: string | null
  category: string | null
  currentPrice: string | null
  collectedAt: string
  sourceUrl: string | null
  mainImageUrl: string | null
  detailImageUrls: string[]
  skuImageUrls: string[]
  skus: ProductSku[]
  attributes: Array<{ name: string; value: string }>
  packageFiles: Array<{ name: string; kind: 'txt' | 'origin-txt' | 'image' }>
  history: ProductHistory[]
}

export interface ProductLibraryQuery {
  keyword: string
  platform: PlatformCode | null
  groupId: string | null
  category: string | null
  page: number
  pageSize: number
}

export interface ProductLibraryPage {
  items: LibraryProduct[]
  total: number
  page: number
  pageSize: number
  categories: string[]
}

export interface ProductLibraryService {
  available: boolean
  mode: 'mock' | 'real'
  groups(): Promise<ProductGroup[]>
  list(query: ProductLibraryQuery): Promise<ProductLibraryPage>
  detail(id: string): Promise<LibraryProduct>
  createGroup(name: string): Promise<ProductGroup>
  moveToGroup(ids: string[], groupId: string | null): Promise<number>
  remove(ids: string[]): Promise<number>
  recollect(ids: string[]): Promise<number>
}
