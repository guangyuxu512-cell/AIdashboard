import { describe, expect, it } from 'vitest'

import { getOfficeSceneTheme } from './office-scene-theme'

describe('office scene theme', () => {
  it('uses independent light and dark semantic palettes', () => {
    const light = getOfficeSceneTheme('light')
    const dark = getOfficeSceneTheme('dark')
    expect(light.floor).not.toBe(dark.floor)
    expect(light.wall).not.toBe(dark.wall)
    expect(light.mainLight).not.toBe(dark.mainLight)
    expect(dark.ambientLightIntensity).toBeGreaterThan(0)
  })
})
