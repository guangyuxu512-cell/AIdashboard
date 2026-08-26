import type { AxiosError } from 'axios'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  apiClient,
  ApiClientError,
  configureApiAuthHooks,
  normalizeApiError,
} from '@/shared/api'

afterEach(() => {
  configureApiAuthHooks({})
})

describe('Mobile API Client', () => {
  it('normalizes the confirmed Backend error envelope', () => {
    const error = {
      isAxiosError: true,
      response: {
        status: 422,
        data: {
          code: 'VALIDATION_ERROR',
          message: '请求参数不合法',
          request_id: 'request-id',
          details: [{ field: 'page' }],
        },
      },
    } as AxiosError

    const normalized = normalizeApiError(error)

    expect(normalized).toBeInstanceOf(ApiClientError)
    expect(normalized).toMatchObject({
      code: 'VALIDATION_ERROR',
      message: '请求参数不合法',
      status: 422,
      requestId: 'request-id',
      details: [{ field: 'page' }],
    })
  })

  it('does not inject authorization before a real Auth provider is configured', async () => {
    let authorizationHeader: unknown

    await apiClient.request({
      adapter: async (config) => {
        authorizationHeader = config.headers.get('Authorization')
        return {
          data: null,
          status: 204,
          statusText: 'No Content',
          headers: {},
          config,
        }
      },
    })

    expect(authorizationHeader).toBeUndefined()
  })

  it('keeps Authorization injection behind an explicit provider hook', async () => {
    configureApiAuthHooks({
      getAuthorizationHeader: () => 'FutureAuth credential',
    })
    let authorizationHeader: unknown

    await apiClient.request({
      adapter: async (config) => {
        authorizationHeader = config.headers.get('Authorization')
        return {
          data: null,
          status: 204,
          statusText: 'No Content',
          headers: {},
          config,
        }
      },
    })

    expect(authorizationHeader).toBe('FutureAuth credential')
  })

  it('calls the reserved unauthorized hook for an HTTP 401 response', async () => {
    const onUnauthorized = vi.fn()
    configureApiAuthHooks({ onUnauthorized })

    await expect(
      apiClient.request({
        adapter: async () =>
          Promise.reject({
            isAxiosError: true,
            response: {
              status: 401,
              data: null,
            },
          }),
      }),
    ).rejects.toBeInstanceOf(ApiClientError)

    expect(onUnauthorized).toHaveBeenCalledOnce()
  })
})
