import axios, { AxiosError } from 'axios'

import { apiBaseUrl, apiTimeoutMs } from './config'
import type { ApiErrorResponseDto } from './contracts'

const HUMAN_SESSION_ERROR_CODES = new Set([
  'HUMAN_AUTHENTICATION_REQUIRED',
  'HUMAN_SESSION_INVALID',
  'HUMAN_USER_DISABLED',
])

let activeTeamIdProvider: () => string | null = () => null
let humanSessionInvalidHandler: ((error: ApiError) => void) | null = null

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

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error
  if (error instanceof AxiosError) {
    const payload = error.response?.data as ApiErrorResponseDto | undefined
    const transportCode =
      error.code === 'ERR_CANCELED'
        ? 'REQUEST_CANCELLED'
        : error.code === 'ECONNABORTED'
          ? 'REQUEST_TIMEOUT'
          : undefined
    return new ApiError({
      message:
        payload?.message ??
        (transportCode === 'REQUEST_CANCELLED'
          ? '请求已取消'
          : transportCode === 'REQUEST_TIMEOUT'
            ? '请求超时'
            : error.response
              ? '请求失败'
              : '无法连接到服务'),
      code: payload?.code ?? transportCode,
      requestId: payload?.request_id,
      status: error.response?.status,
      details: payload?.details,
    })
  }
  return new ApiError({
    message: error instanceof Error ? error.message : '发生未知错误',
  })
}

export async function toResponseApiError(error: unknown): Promise<ApiError> {
  if (error instanceof ApiError) return error
  if (error instanceof AxiosError) {
    const blobPayload = error.response?.data
    if (
      blobPayload &&
      typeof blobPayload === 'object' &&
      'text' in blobPayload &&
      typeof blobPayload.text === 'function'
    ) {
      try {
        const parsed = JSON.parse(await blobPayload.text()) as unknown
        if (
          parsed &&
          typeof parsed === 'object' &&
          typeof (parsed as ApiErrorResponseDto).message === 'string'
        ) {
          const payload = parsed as ApiErrorResponseDto
          return new ApiError({
            message: payload.message,
            code: payload.code,
            requestId: payload.request_id,
            status: error.response?.status,
            details: payload.details,
          })
        }
      } catch {
        // A binary endpoint may return a non-JSON error body. Fall through to
        // the safe generic client error instead of exposing response content.
      }
    }
  }
  return toApiError(error)
}

export const httpClient = axios.create({
  baseURL: apiBaseUrl,
  timeout: apiTimeoutMs,
  withCredentials: true,
  headers: { Accept: 'application/json' },
})

httpClient.interceptors.request.use((config) => {
  const activeTeamId = activeTeamIdProvider()
  if (activeTeamId) config.headers.set('X-Team-ID', activeTeamId)
  return config
})

httpClient.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    const apiError = await toResponseApiError(error)
    if (HUMAN_SESSION_ERROR_CODES.has(apiError.code)) {
      humanSessionInvalidHandler?.(apiError)
    }
    return Promise.reject(apiError)
  },
)

export function configureHumanRequestContext(options: {
  getActiveTeamId: () => string | null
  onSessionInvalid: (error: ApiError) => void
}): void {
  activeTeamIdProvider = options.getActiveTeamId
  humanSessionInvalidHandler = options.onSessionInvalid
}

export function isHumanSessionError(error: unknown): boolean {
  return error instanceof ApiError && HUMAN_SESSION_ERROR_CODES.has(error.code)
}

export function getErrorMessage(error: unknown): string {
  return toApiError(error).message
}
