import { describe, expect, it } from 'vitest'

import { isAiTemplatesVisualMockEnabled } from './visual-mock-gate'

describe('AI templates visual mock gate', () => {
  it('requires development mode and the exact explicit query value', () => {
    expect(isAiTemplatesVisualMockEnabled(true, '1')).toBe(true)
    expect(isAiTemplatesVisualMockEnabled(false, '1')).toBe(false)
    expect(isAiTemplatesVisualMockEnabled(true, undefined)).toBe(false)
    expect(isAiTemplatesVisualMockEnabled(true, 'true')).toBe(false)
    expect(isAiTemplatesVisualMockEnabled(true, ['1'])).toBe(false)
  })
})
