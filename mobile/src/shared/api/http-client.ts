import axios, { AxiosHeaders, type AxiosResponse } from 'axios'

import { getApiAuthHooks } from './auth-hooks'
import { apiBaseUrl, apiTimeoutMs } from './config'
import type { ApiErrorDetailsDto, ApiErrorResponseDto } from './contracts'

export class ApiClientError extends Error {
  readonly code: string | null
  readonly status: number | null
  readonly requestId: string | null
  readonly details: ApiErrorDetailsDto

  constructor(options: {
    message: string
    code?: string | null
    status?: number | null
    requestId?: string | null
    details?: ApiErrorDetailsDto
  }) {
    super(options.message)
    this.name = 'ApiClientError'
    this.code = options.code ?? null
    this.status = options.status ?? null
    this.requestId = options.requestId ?? null
    this.details = options.details ?? null
  }
}

function isApiErrorResponse(value: unknown): value is ApiErrorResponseDto {
  if (!value || typeof value !== 'object') return false
  const payload = value as Partial<ApiErrorResponseDto>
  return (
    typeof payload.code === 'string' &&
    typeof payload.message === 'string' &&
    typeof payload.request_id === 'string'
  )
}

export function normalizeApiError(error: unknown): ApiClientError {
  if (error instanceof ApiClientError) return error
  if (!axios.isAxiosError(error)) {
    return new ApiClientError({ message: '请求失败，请稍后重试' })
  }

  const payload = error.response?.data
  if (isApiErrorResponse(payload)) {
    return new ApiClientError({
      message: payload.message,
      code: payload.code,
      status: error.response?.status ?? null,
      requestId: payload.request_id,
      details: payload.details,
    })
  }

  return new ApiClientError({
    message: '请求失败，请稍后重试',
    status: error.response?.status ?? null,
  })
}

export const apiClient = axios.create({
  baseURL: apiBaseUrl,
  timeout: apiTimeoutMs,
})

function hasJsonResponse(response: AxiosResponse): boolean {
  if (response.status === 204) return true

  const contentType = String(
    response.headers['content-type'] ?? '',
  ).toLowerCase()
  return (
    contentType.includes('application/json') || contentType.includes('+json')
  )
}

apiClient.interceptors.request.use(async (config) => {
  const authorizationHeader = await getApiAuthHooks().getAuthorizationHeader?.()
  if (authorizationHeader) {
    const headers = AxiosHeaders.from(config.headers)
    headers.set('Authorization', authorizationHeader)
    config.headers = headers
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => {
    if (hasJsonResponse(response)) return response

    return Promise.reject(
      new ApiClientError({
        message: '请求失败，请稍后重试',
        status: response.status,
      }),
    )
  },
  async (error: unknown) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      await getApiAuthHooks().onUnauthorized?.()
    }
    return Promise.reject(normalizeApiError(error))
  },
)
