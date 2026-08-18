import { describe, expect, it } from 'vitest'

import { createMockShopSessionDataSource } from './session-data-source'

describe('shop session data source', () => {
  it('exposes metadata only for a session that is not configured', async () => {
    const session = await createMockShopSessionDataSource().getForShop('shop-1')

    expect(session).toEqual({
      sessionId: null,
      configured: false,
      status: 'not_configured',
      version: 0,
      sourceDeviceId: null,
      sourceDeviceName: null,
      capturedAtDisplay: null,
      validatedAtDisplay: null,
      expiresAtDisplay: null,
    })
    expect(JSON.stringify(session)).not.toMatch(/cookie|payload/i)
  })
})
