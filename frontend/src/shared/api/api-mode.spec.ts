import { describe, expect, it } from 'vitest'

import { resolveApiMode } from './api-mode'

describe('resolveApiMode', () => {
  it('accepts explicitly selected mock and real modes', () => {
    expect(resolveApiMode('mock')).toBe('mock')
    expect(resolveApiMode('real')).toBe('real')
  })

  it('rejects missing and invalid modes instead of falling back to mock', () => {
    expect(() => resolveApiMode(undefined)).toThrow('必须显式设置')
    expect(() => resolveApiMode('invalid')).toThrow('不支持')
  })
})
