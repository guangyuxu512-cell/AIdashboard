import { describe, expect, it, vi } from 'vitest'
import { AxiosError, AxiosHeaders } from 'axios'
import type { AxiosResponse } from 'axios'

import {
  ApiError,
  configureHumanRequestContext,
  httpClient,
  isHumanSessionError,
  toResponseApiError,
} from './http-client'

describe('Human request context', () => {
  it('removes a stale team header when switching back to global', async () => {
    configureHumanRequestContext({
      getActiveTeamId: () => null,
      onSessionInvalid: () => undefined,
    })
    let teamHeader: unknown
    await httpClient.get('/api/v1/test', {
      headers: { 'X-Team-ID': 'previous-team' },
      adapter: async (config) => {
        teamHeader = config.headers.get('X-Team-ID')
        return {
          data: {},
          status: 200,
          statusText: 'OK',
          headers: { 'content-type': 'application/json' },
          config,
        }
      },
    })
    expect(teamHeader).toBeUndefined()
  })
  it('sends credentials and injects the selected team centrally', async () => {
    let capturedTeamHeader: unknown
    configureHumanRequestContext({
      getActiveTeamId: () => 'team-1',
      onSessionInvalid: () => undefined,
    })

    await httpClient.get('/api/v1/test', {
      adapter: async (config): Promise<AxiosResponse> => {
        capturedTeamHeader = config.headers.get('X-Team-ID')
        return {
          data: {},
          status: 200,
          statusText: 'OK',
          headers: { 'content-type': 'application/json' },
          config,
        }
      },
    })

    expect(httpClient.defaults.withCredentials).toBe(true)
    expect(capturedTeamHeader).toBe('team-1')
  })

  it('only classifies formal human session error codes', () => {
    const handler = vi.fn()
    configureHumanRequestContext({
      getActiveTeamId: () => null,
      onSessionInvalid: handler,
    })

    expect(
      isHumanSessionError(
        new ApiError({ code: 'HUMAN_SESSION_INVALID', message: 'expired' }),
      ),
    ).toBe(true)
    expect(
      isHumanSessionError(
        new ApiError({
          code: 'WORKER_AUTHENTICATION_FAILED',
          message: 'worker',
        }),
      ),
    ).toBe(false)
  })

  it('classifies a readable Blob download error envelope without exposing binary content', async () => {
    const error = new AxiosError('download failed')
    error.response = {
      // jsdom's Blob lacks `text()`, unlike the browser Blob received by Axios.
      // This is the minimal readable Blob shape used by the response interceptor.
      data: {
        text: async () =>
          JSON.stringify({
          code: 'ASSET_NOT_FOUND',
          message: '图片不存在',
          request_id: 'request-download-1',
          }),
      },
      status: 404,
      statusText: 'Not Found',
      headers: {},
      config: { headers: new AxiosHeaders() },
    }

    await expect(toResponseApiError(error)).resolves.toMatchObject({
      code: 'ASSET_NOT_FOUND',
      message: '图片不存在',
      requestId: 'request-download-1',
      status: 404,
    })
  })

  it('rejects an HTML 200 fallback without expiring Human auth', async () => {
    const onSessionInvalid = vi.fn()
    configureHumanRequestContext({
      getActiveTeamId: () => null,
      onSessionInvalid,
    })

    await expect(
      httpClient.request({
        adapter: async (config): Promise<AxiosResponse> => ({
          data: '<!doctype html><html></html>',
          status: 200,
          statusText: 'OK',
          headers: { 'content-type': 'text/html' },
          config,
        }),
      }),
    ).rejects.toMatchObject({
      name: 'ApiError',
      message: '请求失败',
      status: 200,
    })
    expect(onSessionInvalid).not.toHaveBeenCalled()
  })

  it('accepts JSON, empty and explicitly binary responses', async () => {
    const jsonResponse = await httpClient.request({
      adapter: async (config): Promise<AxiosResponse> => ({
        data: { ok: true },
        status: 200,
        statusText: 'OK',
        headers: { 'content-type': 'application/json; charset=utf-8' },
        config,
      }),
    })
    const emptyResponse = await httpClient.request({
      adapter: async (config): Promise<AxiosResponse> => ({
        data: undefined,
        status: 204,
        statusText: 'No Content',
        headers: {},
        config,
      }),
    })
    const blob = new Blob(['asset'], { type: 'image/png' })
    const blobResponse = await httpClient.request({
      responseType: 'blob',
      adapter: async (config): Promise<AxiosResponse> => ({
        data: blob,
        status: 200,
        statusText: 'OK',
        headers: { 'content-type': 'image/png' },
        config,
      }),
    })

    expect(jsonResponse.data).toEqual({ ok: true })
    expect(emptyResponse.status).toBe(204)
    expect(blobResponse.data).toBe(blob)
  })
})
