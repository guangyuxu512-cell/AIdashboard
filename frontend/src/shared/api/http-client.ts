import axios, { AxiosError } from 'axios'

import { apiBaseUrl, apiTimeoutMs } from './config'
import type { ApiErrorResponseDto } from './contracts'

export class ApiError extends Error {
  readonly code: string
  readonly requestId: string | null
  readonly status: number | null
  readonly details: ApiErrorResponseDto['details']

  constructor(options: {
    message: string
    code?: string
    requestId?: string | null
    status?: number | null
    details?: ApiErrorResponseDto['details']
  }) {
    super(options.message)
    this.name = 'ApiError'
    this.code = options.code ?? 'NETWORK_ERROR'
    this.requestId = options.requestId ?? null
    this.status = options.status ?? null
    this.details = options.details
  }
}

function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error
  if (error instanceof AxiosError) {
    const payload = error.response?.data as ApiErrorResponseDto | undefined
    return new ApiError({
      message:
        payload?.message ?? (error.response ? '请求失败' : '无法连接到服务'),
      code: payload?.code,
      requestId: payload?.request_id,
      status: error.response?.status,
      details: payload?.details,
    })
  }
  return new ApiError({
    message: error instanceof Error ? error.message : '发生未知错误',
  })
}

export const httpClient = axios.create({
  baseURL: apiBaseUrl,
  timeout: apiTimeoutMs,
  headers: { Accept: 'application/json' },
})

httpClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => Promise.reject(toApiError(error)),
)

export function getErrorMessage(error: unknown): string {
  return toApiError(error).message
}
