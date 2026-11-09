import { AxiosError, type AxiosAdapter } from 'axios'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { httpClient } from '@/shared/api'
import { shopSessionApi } from './session-api'

function delayedAdapter(delay: number): AxiosAdapter {
  return (config) =>
    new Promise((resolve, reject) => {
      const responseTimer = setTimeout(() => {
        clearTimeout(timeoutTimer)
        resolve({
          data: {
            shop_id: 'synthetic-shop',
            lease_id: 'synthetic-lease',
            expected_version: 1,
            expires_at: '2026-11-09T12:00:00Z',
          },
          status: 201,
          statusText: 'Created',
          headers: { 'content-type': 'application/json' },
          config,
        })
      }, delay)
      const timeoutTimer = setTimeout(() => {
        clearTimeout(responseTimer)
        reject(new AxiosError('synthetic timeout', 'ECONNABORTED', config))
      }, config.timeout)
    })
}

describe('shop session lease request timeout', () => {
  const originalAdapter = httpClient.defaults.adapter
  beforeEach(() => {
    vi.useFakeTimers()
    httpClient.defaults.adapter = delayedAdapter(15_000)
  })
  afterEach(() => {
    httpClient.defaults.adapter = originalAdapter
    vi.useRealTimers()
  })

  it('receives a lease after 10 seconds while its caller is still waiting', async () => {
    let settled = false
    const pending = shopSessionApi.acquireRefreshLease('synthetic-shop')
    void pending.then(
      () => (settled = true),
      () => (settled = true),
    )
    await vi.advanceTimersByTimeAsync(10_001)
    expect(settled).toBe(false)
    await vi.advanceTimersByTimeAsync(4_999)
    expect((await pending).lease_id).toBe('synthetic-lease')
  })

  it('keeps the default 10 second timeout for unrelated metadata reads', async () => {
    const pending = shopSessionApi.getForShop('synthetic-shop').then(
      () => null,
      (error: { code: string }) => error,
    )
    await vi.advanceTimersByTimeAsync(10_000)
    expect(await pending).toMatchObject({ code: 'REQUEST_TIMEOUT' })
  })
})
