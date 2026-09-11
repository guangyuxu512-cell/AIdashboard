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
          headers: {},
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
})
