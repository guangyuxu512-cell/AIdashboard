import { describe, expect, it } from 'vitest'

import { createMobileQueryClient } from '@/app/providers/query-client'

describe('createMobileQueryClient', () => {
  it('uses deterministic foundation defaults', () => {
    const queryClient = createMobileQueryClient()
    const defaults = queryClient.getDefaultOptions()

    expect(defaults.queries?.retry).toBe(false)
    expect(defaults.queries?.refetchOnWindowFocus).toBe(false)
    expect(defaults.mutations?.retry).toBe(false)
  })
})
