import { httpClient, type PageDto } from '@/shared/api'

export type ProductCollectionRequestStatus =
  'pending' | 'running' | 'partial' | 'succeeded' | 'failed' | 'canceled'

export type ProductCollectionItemState =
  | 'pending_dispatch'
  | 'dispatching'
  | 'dispatched'
  | 'running'
  | 'received'
  | 'processing'
  | 'succeeded'
  | 'failed'
  | 'canceled'

export interface ProductCollectionItemDto {
  item_id: string
  candidate_id: string | null
  platform: 'douyin' | 'pinduoduo'
  source_product_id: string
  collection_mode: 'auto_gateway' | 'manual_return'
  state: ProductCollectionItemState
  library_product_id: string | null
  attempt_count: number
  last_error_code: string | null
  last_error_stage: string | null
  last_error_message: string | null
  created_at: string
  updated_at: string
  finished_at: string | null
}

export interface ProductCollectionRequestDto {
  request_id: string
  submission_key: string
  source_kind: 'manual' | 'selection_candidates'
  target_group_id: string | null
  status: ProductCollectionRequestStatus
  item_count: number
  pending_count: number
  running_count: number
  succeeded_count: number
  failed_count: number
  canceled_count: number
  cancel_requested_at: string | null
  created_at: string
  updated_at: string
  finished_at: string | null
  items: ProductCollectionItemDto[] | null
}

export interface ProductCollectionReceiptDto {
  request_id: string
  status: ProductCollectionRequestStatus
  item_count: number
  reused: boolean
}

export type ProductCollectionCreateDto = {
  submission_key: string
  target_group_id?: string | null
  source:
    | {
        kind: 'manual'
        targets: Array<{
          platform: 'douyin' | 'pinduoduo'
          product_id_or_supported_url: string
        }>
      }
    | { kind: 'selection_candidates'; candidate_ids: string[] }
}

const requestPath = '/api/v1/product-collection/requests'

export async function createProductCollectionRequest(
  command: ProductCollectionCreateDto,
): Promise<ProductCollectionReceiptDto> {
  return (
    await httpClient.post<ProductCollectionReceiptDto>(requestPath, command)
  ).data
}

export async function listProductCollectionRequests(params: {
  page: number
  pageSize: number
}): Promise<PageDto<ProductCollectionRequestDto>> {
  return (
    await httpClient.get<PageDto<ProductCollectionRequestDto>>(requestPath, {
      params: { page: params.page, page_size: params.pageSize },
    })
  ).data
}

export async function readProductCollectionRequest(
  requestId: string,
): Promise<ProductCollectionRequestDto> {
  return (
    await httpClient.get<ProductCollectionRequestDto>(
      `${requestPath}/${encodeURIComponent(requestId)}`,
    )
  ).data
}

export async function cancelProductCollectionRequest(
  requestId: string,
): Promise<ProductCollectionRequestDto> {
  return (
    await httpClient.post<ProductCollectionRequestDto>(
      `${requestPath}/${encodeURIComponent(requestId)}/cancel`,
    )
  ).data
}

export async function retryProductCollectionItem(
  itemId: string,
): Promise<ProductCollectionRequestDto> {
  return (
    await httpClient.post<ProductCollectionRequestDto>(
      `/api/v1/product-collection/items/${encodeURIComponent(itemId)}/retry`,
    )
  ).data
}

export async function recaptureProductCollectionItem(
  itemId: string,
): Promise<ProductCollectionRequestDto> {
  return (
    await httpClient.post<ProductCollectionRequestDto>(
      `/api/v1/product-collection/items/${encodeURIComponent(itemId)}/recapture`,
    )
  ).data
}

export async function submitCandidateCollectionRequest(
  candidateIds: string[],
  submissionKey: string,
): Promise<ProductCollectionReceiptDto> {
  return createProductCollectionRequest({
    submission_key: submissionKey,
    source: {
      kind: 'selection_candidates',
      candidate_ids: candidateIds,
    },
  })
}
