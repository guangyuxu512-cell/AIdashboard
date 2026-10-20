import { httpClient, type PageDto } from '@/shared/api'
import type {
  LibraryProduct,
  ProductGroup,
  ProductLibraryService,
} from '../model/contracts'

interface ProductLibraryGroupDto {
  group_id: string
  name: string
}

interface ProductLibraryProductDto {
  product_id: string
  platform: 'douyin' | 'pinduoduo'
  source_product_id: string
  group_id: string | null
  title: string | null
  source_url: string | null
  primary_image_url: string | null
  category_path: string[] | null
  current_sale_price_cent: number | null
  currency: string | null
  adopted_version_id: string | null
  last_applied_capture_at: string | null
  last_ingested_at: string | null
  created_at: string
  updated_at: string
}

interface ProductLibraryVersionDto {
  version_id: string
  captured_at: string
  source_format_version: number
  cleaner_version: string
  raw_content_sha256: string
  uu_snapshot: Record<string, unknown>
  price_evidence: Record<string, unknown>
}

interface ProductLibraryProductDetailDto extends ProductLibraryProductDto {
  merchant_snapshot: Record<string, unknown> | null
  versions: ProductLibraryVersionDto[]
  latest_collection_state: string | null
  latest_collection_error_code: string | null
}

const groupsPath = '/api/v1/product-library/groups'
const productsPath = '/api/v1/product-library/products'

function price(value: number | null): string | null {
  if (value === null) return null
  return (value / 100).toFixed(2)
}

function platform(value: ProductLibraryProductDto['platform']) {
  return value === 'pinduoduo' ? ('pdd' as const) : value
}

function mapProduct(
  dto: ProductLibraryProductDto,
  groupNames: ReadonlyMap<string, string>,
  detail?: ProductLibraryProductDetailDto,
): LibraryProduct {
  return {
    id: dto.product_id,
    productId: dto.source_product_id,
    platform: platform(dto.platform),
    title: dto.title ?? '—',
    groupId: dto.group_id,
    groupName: dto.group_id ? (groupNames.get(dto.group_id) ?? null) : null,
    category: dto.category_path?.join(' / ') ?? null,
    currentPrice: price(dto.current_sale_price_cent),
    currency: dto.currency,
    collectedAt:
      dto.last_applied_capture_at ?? dto.last_ingested_at ?? dto.updated_at,
    sourceUrl: dto.source_url,
    mainImageUrl: dto.primary_image_url,
    detailImageUrls: [],
    specDimensions: [],
    skus: [],
    attributes: [],
    mockEditedAt: null,
    packageFiles: [],
    history:
      detail?.versions.map((version) => ({
        id: version.version_id,
        collectedAt: version.captured_at,
        state: 'completed' as const,
        summary: `资料版本 ${version.source_format_version} · 清洗器 ${version.cleaner_version}`,
      })) ?? [],
    latestCollectionState: detail?.latest_collection_state ?? null,
    latestCollectionErrorCode: detail?.latest_collection_error_code ?? null,
  }
}

export function createProductLibraryRealService(): ProductLibraryService {
  let groupNames = new Map<string, string>()
  const writeUnavailable = async (): Promise<never> => {
    throw new Error('商品库写入、分组维护与导入导出尚未接入正式接口')
  }
  return {
    available: true,
    mode: 'real',
    capabilities: {
      platformFilter: false,
      categoryFilter: false,
      edit: false,
      createGroup: false,
      moveGroup: false,
      remove: false,
      recollect: false,
      import: false,
      export: false,
    },
    async groups(): Promise<ProductGroup[]> {
      const rows = (await httpClient.get<ProductLibraryGroupDto[]>(groupsPath))
        .data
      groupNames = new Map(rows.map((row) => [row.group_id, row.name]))
      return rows.map((row) => ({
        id: row.group_id,
        name: row.name,
        count: null,
      }))
    },
    async list(query) {
      if (query.platform || query.category)
        throw new Error('正式商品库接口暂不支持平台或类目筛选')
      if (query.view === 'grouped' && !query.groupId)
        return {
          items: [],
          total: 0,
          page: 1,
          pageSize: query.pageSize,
          categories: [],
        }
      const response = (
        await httpClient.get<PageDto<ProductLibraryProductDto>>(productsPath, {
          params: {
            page: query.page,
            page_size: query.pageSize,
            search: query.keyword || undefined,
            group_id:
              query.view === 'grouped'
                ? (query.groupId ?? undefined)
                : undefined,
            ungrouped: query.view === 'ungrouped' || undefined,
          },
        })
      ).data
      return {
        items: response.items.map((row) => mapProduct(row, groupNames)),
        total: response.total,
        page: response.page,
        pageSize: response.page_size,
        categories: [],
      }
    },
    async detail(id) {
      const dto = (
        await httpClient.get<ProductLibraryProductDetailDto>(
          `${productsPath}/${encodeURIComponent(id)}`,
        )
      ).data
      return mapProduct(dto, groupNames, dto)
    },
    saveEdit: writeUnavailable,
    createGroup: writeUnavailable,
    moveToGroup: writeUnavailable,
    remove: writeUnavailable,
    recollect: writeUnavailable,
  }
}
