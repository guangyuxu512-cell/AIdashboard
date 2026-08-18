import { describe, expect, it } from 'vitest'

import { createMockCredentialDataSource } from './credential-data-source'

describe('credential data source', () => {
  it('stores only safe credential status in the frontend ViewModel', async () => {
    const source = createMockCredentialDataSource()
    const created = await source.create({
      shopId: 'shop-1',
      platform: 'douyin',
      loginIdentifier: '13812348888',
      password: 'stage-3a-password',
      preferredVerificationChannel: 'manual',
    })

    expect(created).toEqual(
      expect.objectContaining({
        maskedIdentifier: '138****8888',
        configured: true,
        passwordConfigured: true,
      }),
    )
    expect(JSON.stringify(created)).not.toContain('stage-3a-password')
    expect(JSON.stringify(created)).not.toContain('13812348888')
  })

  it('preserves the configured password when an update omits it', async () => {
    const source = createMockCredentialDataSource()
    const created = await source.create({
      shopId: 'shop-1',
      platform: 'douyin',
      loginIdentifier: 'first@example.com',
      password: 'initial-password',
      preferredVerificationChannel: 'manual',
    })
    const updated = await source.update({
      credentialId: created.credentialId!,
      loginIdentifier: 'second@example.com',
      preferredVerificationChannel: 'email',
    })

    expect(updated.maskedIdentifier).toBe('sec***@example.com')
    expect(updated.passwordConfigured).toBe(true)
    expect(updated.preferredVerificationChannel).toBe('email')
    expect(JSON.stringify(updated)).not.toContain('initial-password')
  })
})
