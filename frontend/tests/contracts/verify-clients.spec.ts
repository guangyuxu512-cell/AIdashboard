import { writeFileSync } from 'node:fs'
import { AxiosError, AxiosHeaders } from 'axios'
import { afterAll, expect, it, vi } from 'vitest'
import {
  httpClient,
  toApiError,
  configureHumanRequestContext,
} from '../../src/shared/api/http-client'
import {
  apiClient,
  normalizeApiError,
} from '../../../mobile/src/shared/api/http-client'
import { configureHumanRequestContext as configureMobile } from '../../../mobile/src/shared/api/auth-hooks'
import { mapYingdaoInventoryDto } from '../../src/entities/device/api/device-mapper'
import type { DeviceProviderInventoryReadDto } from '../../src/entities/device/api/contracts'

type Finding = {
  rule: string
  contract: string
  expected: unknown
  actual: unknown
}
const findings: Finding[] = []
function check(contract: string, expected: unknown, actual: unknown) {
  if (JSON.stringify(expected) !== JSON.stringify(actual))
    findings.push({ rule: 'runtime-contract', contract, expected, actual })
}
function error(code?: string, data?: unknown, status = 422) {
  const failure = new AxiosError('synthetic transport', code)
  if (data !== undefined)
    failure.response = {
      data,
      status,
      statusText: 'synthetic',
      headers: {},
      config: { headers: new AxiosHeaders() },
    }
  return failure
}

it('records actual timeout/cancellation behavior without sending HTTP', () => {
  for (const [code, expected] of [
    ['ECONNABORTED', 'REQUEST_TIMEOUT'],
    ['ERR_CANCELED', 'REQUEST_CANCELLED'],
  ]) {
    check(`pc:${code}`, expected, toApiError(error(code)).code)
    check(`mobile:${code}`, expected, normalizeApiError(error(code)).code)
  }
})

it('both actual clients preserve formal errors and never expire Human auth for platform errors', async () => {
  const pcLogout = vi.fn(),
    mobileLogout = vi.fn()
  configureHumanRequestContext({
    getActiveTeamId: () => null,
    onSessionInvalid: pcLogout,
  })
  configureMobile({ onSessionInvalid: mobileLogout })
  const payload = {
    code: 'PLATFORM_BUSINESS_REJECTED',
    message: '安全错误',
    request_id: 'synthetic-request',
    details: { zero: 0, flag: false, value: null },
  }
  for (const [name, client] of [
    ['pc', httpClient],
    ['mobile', apiClient],
  ] as const) {
    await expect(
      client.request({
        adapter: async () => Promise.reject(error(undefined, payload, 401)),
      }),
    ).rejects.toMatchObject({
      code: payload.code,
      status: 401,
      requestId: payload.request_id,
      details: payload.details,
    })
    const normalized =
      name === 'pc'
        ? toApiError(error(undefined, { detail: 'synthetic detail' }))
        : normalizeApiError(error(undefined, { detail: 'synthetic detail' }))
    expect(normalized.message).not.toContain('synthetic detail')
    expect(normalized.status).toBe(422)
  }
  expect(pcLogout).not.toHaveBeenCalled()
  expect(mobileLogout).not.toHaveBeenCalled()
  configureHumanRequestContext({
    getActiveTeamId: () => null,
    onSessionInvalid: () => {},
  })
  configureMobile({})
})

it('records HTML 200 rejection with real interceptors and in-memory adapters', async () => {
  for (const [name, client] of [
    ['pc', httpClient],
    ['mobile', apiClient],
  ] as const) {
    let rejected = false
    try {
      await client.request({
        adapter: async (config) => ({
          data: '<html>synthetic fallback</html>',
          status: 200,
          statusText: 'OK',
          headers: { 'content-type': 'text/html' },
          config,
        }),
      })
    } catch {
      rejected = true
    }
    check(`${name}:html-200`, true, rejected)
  }
})

it('records unknown versus false in the existing device mapper; zero is not an empty value', () => {
  const dto = {
    available: true,
    provider_version: null,
    account_display: null,
    account_type: null,
    enterprise_account: null,
    last_discovered_at: '2026-01-01T00:00:00Z',
    inventory: {
      status: 'ready',
      status_reason: null,
      execution_available: false,
      logged_in: false,
      applications: [],
    },
  } as unknown as DeviceProviderInventoryReadDto
  check(
    'pc:enterprise_account:null',
    null,
    mapYingdaoInventoryDto(dto).enterpriseAccount,
  )
  expect(
    mapYingdaoInventoryDto({ ...dto, enterprise_account: false })
      .enterpriseAccount,
  ).toBe(false)
  expect(mapYingdaoInventoryDto(dto).applicationCount).toBe(0)
})

afterAll(() => {
  if (!process.env.VERIFY_PROBE_OUTPUT)
    throw new Error(
      'Run via the root verify command; no implicit baseline file',
    )
  writeFileSync(process.env.VERIFY_PROBE_OUTPUT, JSON.stringify(findings))
})
