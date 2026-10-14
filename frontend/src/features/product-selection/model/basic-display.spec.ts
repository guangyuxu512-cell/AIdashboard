import { describe, expect, it } from 'vitest'
import { basicFailure } from './basic-display'
describe('single basic-info safe failure semantics', () => {
  it('does not guess login/risk or token from an unknown business rejection', () => {
    expect(
      basicFailure(
        'DOUYIN_SELECTION_BUSINESS_REJECTED',
        'platform_business',
        '600002',
      ),
    ).toBe('平台业务拒绝（600002），原因未确定')
    expect(basicFailure('AUTH_INVALID')).toContain('重新登录')
    expect(basicFailure('PLATFORM_SIGNER_FAILED')).toBe('签名失败，可重试')
    expect(basicFailure('PLATFORM_RESPONSE_INVALID')).not.toContain('登录')
  })
})
