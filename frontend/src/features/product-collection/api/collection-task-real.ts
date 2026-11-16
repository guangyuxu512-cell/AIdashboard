import type { PlatformCode } from '@/entities/platform/model/registry'
import type {
  CollectionTask,
  CollectionTaskItem,
  CollectionTaskService,
} from '../model/contracts'
import {
  cancelProductCollectionRequest,
  createProductCollectionRequest,
  listProductCollectionRequests,
  readProductCollectionRequest,
  recaptureProductCollectionItem,
  retryProductCollectionItem,
  type ProductCollectionItemDto,
  type ProductCollectionRequestDto,
} from './product-collection-real-api'

function platform(value: ProductCollectionItemDto['platform']): PlatformCode {
  return value === 'pinduoduo' ? 'pdd' : value
}

function mapItem(dto: ProductCollectionItemDto): CollectionTaskItem {
  return {
    id: dto.item_id,
    candidateId: dto.candidate_id,
    platform: platform(dto.platform),
    productId: dto.source_product_id,
    collectionMode: dto.collection_mode,
    state: dto.state,
    libraryProductId: dto.library_product_id,
    attemptCount: dto.attempt_count,
    errorCode: dto.last_error_code,
    errorStage: dto.last_error_stage,
    errorMessage: dto.last_error_message,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
    finishedAt: dto.finished_at,
  }
}

export function mapCollectionTask(
  dto: ProductCollectionRequestDto,
): CollectionTask {
  const items = dto.items?.map(mapItem) ?? null
  const only = items?.length === 1 ? items[0]! : null
  const platforms = new Set(items?.map((item) => item.platform) ?? [])
  const terminal = dto.succeeded_count + dto.failed_count + dto.canceled_count
  return {
    id: dto.request_id,
    platform: platforms.size === 1 ? [...platforms][0]! : null,
    inputMode:
      dto.source_kind === 'selection_candidates'
        ? 'selection-candidates'
        : 'product',
    inputValue: `${dto.source_kind === 'selection_candidates' ? '候选商品' : '手工商品'} · ${dto.item_count} 项`,
    productId: only?.productId ?? null,
    title: null,
    status: dto.status,
    progress:
      dto.item_count > 0 ? Math.round((terminal / dto.item_count) * 100) : null,
    receiptId: dto.request_id,
    ingestionState:
      dto.status === 'succeeded'
        ? 'ingested'
        : dto.status === 'running'
          ? 'processing'
          : dto.status === 'partial' || dto.status === 'failed'
            ? 'failed'
            : 'not-started',
    errorMessage:
      items?.find((item) => item.errorMessage)?.errorMessage ?? null,
    itemCount: dto.item_count,
    pendingCount: dto.pending_count,
    runningCount: dto.running_count,
    succeededCount: dto.succeeded_count,
    failedCount: dto.failed_count,
    canceledCount: dto.canceled_count,
    items,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}

function assertUnfiltered(query: {
  keyword: string
  platform: PlatformCode | null
  status: string | null
}) {
  if (query.keyword || query.platform || query.status)
    throw new Error('正式采集任务接口暂不支持搜索、平台或状态筛选')
}

export function createCollectionTaskRealService(): CollectionTaskService {
  return {
    available: true,
    mode: 'real',
    supportsListFilters: false,
    supportsShopCode: false,
    supportsAutomaticPdd: false,
    async list(query) {
      assertUnfiltered(query)
      const result = await listProductCollectionRequests(query)
      return {
        items: result.items.map(mapCollectionTask),
        total: result.total,
        page: result.page,
        pageSize: result.page_size,
        counts: null,
      }
    },
    async detail(id) {
      return mapCollectionTask(await readProductCollectionRequest(id))
    },
    async create(input) {
      if (input.inputMode !== 'product')
        throw new Error('正式服务当前仅支持商品 ID 或受支持的商品链接')
      if (input.platform !== 'douyin')
        throw new Error('当前正式自动采集仅支持抖音商品')
      const receipt = await createProductCollectionRequest({
        submission_key: input.submissionKey ?? crypto.randomUUID(),
        source: {
          kind: 'manual',
          targets: input.values.map((value) => ({
            platform: 'douyin',
            product_id_or_supported_url: value,
          })),
        },
      })
      const task = mapCollectionTask(
        await readProductCollectionRequest(receipt.request_id),
      )
      task.reused = receipt.reused
      return {
        created: [task],
        duplicates: receipt.reused
          ? [{ value: input.values.join('、'), taskId: receipt.request_id }]
          : [],
      }
    },
    async retry(ids) {
      let count = 0
      for (const requestId of new Set(ids)) {
        const task = await readProductCollectionRequest(requestId)
        for (const item of task.items ?? []) {
          if (item.state !== 'failed') continue
          await retryProductCollectionItem(item.item_id)
          count += 1
        }
      }
      return count
    },
    async cancel(ids) {
      let count = 0
      for (const requestId of new Set(ids)) {
        const before = await readProductCollectionRequest(requestId)
        if (
          ['partial', 'succeeded', 'failed', 'canceled'].includes(before.status)
        )
          continue
        await cancelProductCollectionRequest(requestId)
        count += 1
      }
      return count
    },
    async retryItem(itemId) {
      return mapCollectionTask(await retryProductCollectionItem(itemId))
    },
    async recaptureItem(itemId) {
      return mapCollectionTask(await recaptureProductCollectionItem(itemId))
    },
  }
}
