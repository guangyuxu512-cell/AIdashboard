export interface PageDto<TItem> {
  items: TItem[]
  total: number
  page: number
  page_size: number
}

export type ApiErrorDetailsDto = Record<string, unknown> | unknown[] | null

export interface ApiErrorResponseDto {
  code: string
  message: string
  request_id: string
  details?: ApiErrorDetailsDto
}
