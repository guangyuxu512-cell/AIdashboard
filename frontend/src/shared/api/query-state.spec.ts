import { describe, expect, it } from 'vitest'

import { isInitialQueryError, isInitialQueryLoading } from './query-state'

describe('query presentation state', () => {
  it('keeps cached data during background loading and failure', () => {
    expect(isInitialQueryLoading(true, undefined)).toBe(true)
    expect(isInitialQueryLoading(true, [])).toBe(false)
    expect(isInitialQueryError(new Error('initial'), undefined)).toBe(true)
    expect(isInitialQueryError(new Error('background'), [])).toBe(false)
  })
})
