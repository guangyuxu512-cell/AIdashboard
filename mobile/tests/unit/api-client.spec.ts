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

  it('rejects a Vite HTML fallback instead of leaving domain queries pending', async () => {
    await expect(
      apiClient.request({
        adapter: async (config) => ({
          data: '<!doctype html><html></html>',
          status: 200,
          statusText: 'OK',
          headers: { 'content-type': 'text/html' },
          config,
        }),
      }),
    ).rejects.toMatchObject({
      name: 'ApiClientError',
      message: '请求失败，请稍后重试',
      status: 200,
    })
  })

  it('accepts a JSON success response and a 204 response', async () => {
    const jsonResponse = await apiClient.request({
      adapter: async (config) => ({
        data: { ok: true },
        status: 200,
        statusText: 'OK',
        headers: { 'content-type': 'application/json; charset=utf-8' },
        config,
      }),
    })
    const noContentResponse = await apiClient.request({
      adapter: async (config) => ({
        data: undefined,
        status: 204,
        statusText: 'No Content',
        headers: {},
        config,
      }),
    })

    expect(jsonResponse.data).toEqual({ ok: true })
    expect(noContentResponse.status).toBe(204)
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
