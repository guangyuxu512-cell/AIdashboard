import { describe, expect, it } from 'vitest'

import { isAiGenerationVisualMockEnabled } from './visual-mock-gate'

describe('AI generation visual mock gate', () => {
  it('enables only the exact development query', () => {
    expect(isAiGenerationVisualMockEnabled(true, '1')).toBe(true)
    expect(isAiGenerationVisualMockEnabled(true, 'true')).toBe(false)
    expect(isAiGenerationVisualMockEnabled(true, ['1'])).toBe(false)
  })

  it('stays disabled in production even with visualMock=1', () => {
    expect(isAiGenerationVisualMockEnabled(false, '1')).toBe(false)
  })
})
