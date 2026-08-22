import { describe, expect, it } from 'vitest'

import { isLogViewportNearEnd } from './log-follow'

describe('task runtime log following', () => {
  it('follows near the bottom and pauses after the user scrolls up', () => {
    expect(isLogViewportNearEnd(1_000, 780, 200)).toBe(true)
    expect(isLogViewportNearEnd(1_000, 500, 200)).toBe(false)
  })
})
