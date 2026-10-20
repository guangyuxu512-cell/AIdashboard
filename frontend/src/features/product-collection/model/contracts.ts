import type { PlatformCode } from '@/entities/platform/model/registry'

export type CollectionTaskStatus =
  'queued' | 'processing' | 'completed' | 'failed' | 'cancelled'

export type CollectionInputMode = 'product' | 'shop-code'

export interface CollectionTask {
  id: string
  platform: PlatformCode
  inputMode: CollectionInputMode
  inputValue: string
  productId: string | null
  title: string | null
  status: CollectionTaskStatus
  progress: number | null
  receiptId: string | null
  ingestionState: 'not-started' | 'processing' | 'ingested' | 'failed'
  errorMessage: string | null
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
  counts: Record<'all' | CollectionTaskStatus, number>
}

export interface CreateCollectionTasksInput {
  platform: PlatformCode
  inputMode: CollectionInputMode
  values: string[]
}

export interface CreateCollectionTasksReceipt {
  created: CollectionTask[]
  duplicates: Array<{ value: string; taskId: string }>
}

export interface CollectionTaskService {
  available: boolean
  mode: 'mock' | 'real'
  list(query: CollectionTaskQuery): Promise<CollectionTaskPage>
  detail(id: string): Promise<CollectionTask>
  create(
    input: CreateCollectionTasksInput,
  ): Promise<CreateCollectionTasksReceipt>
  retry(ids: string[]): Promise<number>
  cancel(ids: string[]): Promise<number>
}

export interface CandidateCollectionDraft {
  candidateId: string
  productId: string
  title: string
  platform?: PlatformCode
}
