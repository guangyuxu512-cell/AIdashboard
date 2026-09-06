import type { AxiosError } from 'axios'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  apiClient,
  ApiClientError,
  configureHumanRequestContext,
  normalizeApiError,
} from '@/shared/api'

afterEach(() => {
  configureHumanRequestContext({})
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

  it('uses credentialed requests without injecting a Worker or JWT authorization header', async () => {
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

    expect(apiClient.defaults.withCredentials).toBe(true)
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

  it('injects the selected team centrally', async () => {
    configureHumanRequestContext({
      getActiveTeamId: () => 'team-1',
    })
    let teamHeader: unknown

    await apiClient.request({
      adapter: async (config) => {
        teamHeader = config.headers.get('X-Team-ID')
        return {
          data: null,
          status: 204,
          statusText: 'No Content',
          headers: {},
          config,
        }
      },
    })

    expect(teamHeader).toBe('team-1')
  })

  it('expires auth only for formal Human Session error codes', async () => {
    const onSessionInvalid = vi.fn()
    configureHumanRequestContext({ onSessionInvalid })

    await expect(
      apiClient.request({
        adapter: async () =>
          Promise.reject({
            isAxiosError: true,
            response: {
              status: 401,
              data: {
                code: 'HUMAN_SESSION_INVALID',
                message: '登录会话已失效，请重新登录',
                request_id: 'session-request',
              },
            },
          }),
      }),
    ).rejects.toBeInstanceOf(ApiClientError)

    expect(onSessionInvalid).toHaveBeenCalledOnce()

    await expect(
      apiClient.request({
        adapter: async () =>
          Promise.reject({
            isAxiosError: true,
            response: {
              status: 401,
              data: {
                code: 'HUMAN_LOGIN_FAILED',
                message: '登录账号或密码错误',
                request_id: 'login-request',
              },
            },
          }),
      }),
    ).rejects.toBeInstanceOf(ApiClientError)

    expect(onSessionInvalid).toHaveBeenCalledOnce()
  })
})
