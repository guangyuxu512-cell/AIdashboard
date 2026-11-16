import { writeFileSync } from 'node:fs'
import { AxiosError, AxiosHeaders } from 'axios'
import { afterAll, expect, it, vi } from 'vitest'
import {
  httpClient,
  toApiError,
  configureHumanRequestContext,
} from '../../src/shared/api/http-client'
import { mapDeviceDto } from '../../src/entities/device/api/device-mapper'
import { deviceApi } from '../../src/entities/device/api/device-api'
import type { DeviceReadDto } from '../../src/entities/device/api/contracts'

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
  }
})

it('the desktop client preserves formal errors and does not expire Human auth for platform errors', async () => {
  const pcLogout = vi.fn()
  configureHumanRequestContext({
    getActiveTeamId: () => null,
    onSessionInvalid: pcLogout,
  })
  const payload = {
    code: 'PLATFORM_BUSINESS_REJECTED',
    message: '安全错误',
    request_id: 'synthetic-request',
    details: { zero: 0, flag: false, value: null },
  }
  await expect(
    httpClient.request({
      adapter: async () => Promise.reject(error(undefined, payload, 401)),
    }),
  ).rejects.toMatchObject({
    code: payload.code,
    status: 401,
    requestId: payload.request_id,
    details: payload.details,
  })
  const normalized = toApiError(
    error(undefined, { detail: 'synthetic detail' }),
  )
  expect(normalized.message).not.toContain('synthetic detail')
  expect(normalized.status).toBe(422)
  expect(pcLogout).not.toHaveBeenCalled()
  configureHumanRequestContext({
    getActiveTeamId: () => null,
    onSessionInvalid: () => {},
  })
})

it('records HTML 200 rejection with the real desktop interceptor and in-memory adapter', async () => {
  let rejected = false
  try {
    await httpClient.request({
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
  check('pc:html-200', true, rejected)
})

it('keeps a missing Worker distinct from an enabled device and preserves false', () => {
  const dto: DeviceReadDto = {
    device_id: 'synthetic-device',
    display_name: 'synthetic',
    enabled: true,
    location: null,
    note: null,
    deleted_at: null,
    worker_runtime: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  }
  check('pc:worker-runtime:missing', 'unavailable', mapDeviceDto(dto).runtimeStatus)
  expect(mapDeviceDto({ ...dto, enabled: false }).enabledStatus).toBe('disabled')
})

it('reads the Worker-reported shop inventory through the device API', async () => {
  const inventory = { device_id: 'synthetic-device', available: true, last_discovered_at: null, shops: [] }
  const get = vi.spyOn(httpClient, 'get').mockResolvedValueOnce({ data: inventory } as never)
  await expect(deviceApi.getLocalShops('synthetic-device')).resolves.toEqual(inventory)
  check('pc:worker-local-shops:path', '/api/v1/devices/synthetic-device/local-shops', get.mock.calls[0]?.[0])
  get.mockRestore()
})

afterAll(() => {
  if (!process.env.VERIFY_PROBE_OUTPUT)
    throw new Error(
      'Run via the root verify command; no implicit baseline file',
    )
  writeFileSync(process.env.VERIFY_PROBE_OUTPUT, JSON.stringify(findings))
})
