import { describe, expect, it } from 'vitest'

import source from './PlatformDisplay.vue?raw'

describe('PlatformDisplay alignment contract', () => {
  it('uses one fixed centered icon slot before a left-aligned label', () => {
    expect(source).toMatch(
      /platform-display__icon-slot[\s\S]*PlatformIcon[\s\S]*platform-display__label/,
    )
    expect(source).toMatch(
      /\.platform-display__icon-slot[\s\S]*width: var\(--space-5\)[\s\S]*height: var\(--space-5\)[\s\S]*flex: 0 0 var\(--space-5\)[\s\S]*place-items: center/,
    )
    expect(source).toMatch(/\.platform-display[\s\S]*gap: var\(--space-2\)/)
    expect(source).toMatch(/\.platform-display[\s\S]*vertical-align: middle/)
    expect(source).toMatch(/\.platform-display__label[\s\S]*text-align: left/)
  })
})
