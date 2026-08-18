export interface PageDto<Item> {
  items: Item[]
  total: number
  page: number
  page_size: number
}

export interface PageResult<Item> {
  items: Item[]
  total: number
  page: number
  pageSize: number
}

export interface PageParams {
  page: number
  pageSize: number
}

export interface ApiErrorResponseDto {
  code: string
  message: string
  request_id: string
  details?: Record<string, unknown> | unknown[] | null
}
