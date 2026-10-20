import type { PlatformCode } from '@/entities/platform/model/registry'

export type CollectionTaskStatus =
  'pending' | 'running' | 'partial' | 'succeeded' | 'failed' | 'canceled'

export type CollectionInputMode =
  'product' | 'shop-code' | 'selection-candidates'

export interface CollectionTaskItem {
  id: string
  candidateId: string | null
  platform: PlatformCode
  productId: string
  collectionMode: 'auto_gateway' | 'manual_return'
  state: string
  libraryProductId: string | null
  attemptCount: number
  errorCode: string | null
  errorStage: string | null
  errorMessage: string | null
  createdAt: string
  updatedAt: string
  finishedAt: string | null
}

export interface CollectionTask {
  id: string
  platform: PlatformCode | null
  inputMode: CollectionInputMode
  inputValue: string
  productId: string | null
  title: string | null
  status: CollectionTaskStatus
  progress: number | null
  receiptId: string | null
  ingestionState: 'not-started' | 'processing' | 'ingested' | 'failed'
  errorMessage: string | null
  itemCount: number
  pendingCount: number
  runningCount: number
  succeededCount: number
  failedCount: number
  canceledCount: number
  reused?: boolean
  items: CollectionTaskItem[] | null
  createdAt: string
  updatedAt: string
}

export interface CollectionTaskQuery {
  keyword: string
  platform: PlatformCode | null
  status: CollectionTaskStatus | null
  page: number
  pageSize: number
}

export interface CollectionTaskPage {
  items: CollectionTask[]
  total: number
  page: number
  pageSize: number
  counts: Record<'all' | CollectionTaskStatus, number> | null
}

export interface CreateCollectionTasksInput {
  platform: PlatformCode
  inputMode: CollectionInputMode
  values: string[]
  submissionKey?: string
}

export interface CreateCollectionTasksReceipt {
  created: CollectionTask[]
  duplicates: Array<{ value: string; taskId: string }>
}

export interface CollectionTaskService {
  available: boolean
  mode: 'mock' | 'real'
  supportsListFilters: boolean
  supportsShopCode: boolean
  supportsAutomaticPdd: boolean
  list(query: CollectionTaskQuery): Promise<CollectionTaskPage>
  detail(id: string): Promise<CollectionTask>
  create(
    input: CreateCollectionTasksInput,
  ): Promise<CreateCollectionTasksReceipt>
  retry(ids: string[]): Promise<number>
  cancel(ids: string[]): Promise<number>
  retryItem(itemId: string): Promise<CollectionTask>
  recaptureItem(itemId: string): Promise<CollectionTask>
}

export interface CandidateCollectionDraft {
  candidateId: string
  productId: string
  title: string
  platform?: PlatformCode
}
