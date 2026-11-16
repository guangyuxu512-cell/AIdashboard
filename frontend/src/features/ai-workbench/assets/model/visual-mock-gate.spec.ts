import { describe, expect, it } from 'vitest'

import { isAiAssetsVisualMockEnabled } from './visual-mock-gate'

describe('AI assets visual mock gate', () => {
  it('requires development mode and the exact explicit query value', () => {
    expect(isAiAssetsVisualMockEnabled(true, '1')).toBe(true)
    expect(isAiAssetsVisualMockEnabled(false, '1')).toBe(false)
    expect(isAiAssetsVisualMockEnabled(true, undefined)).toBe(false)
    expect(isAiAssetsVisualMockEnabled(true, 'true')).toBe(false)
    expect(isAiAssetsVisualMockEnabled(true, ['1'])).toBe(false)
  })
})
