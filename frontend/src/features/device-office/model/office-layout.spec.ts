import { describe, expect, it } from 'vitest'

import {
  getWorkstationSlot,
  OFFICE_DESIGN_CANVAS,
  WORKSTATION_RENDER_SIZE,
  WORKSTATION_SLOTS,
  WORKSTATION_SOURCE_CANVAS,
} from './office-layout'

describe('official device office V2 layout', () => {
  it('uses one 1440 × 810 canvas and the canonical 4:3 station geometry', () => {
    expect(OFFICE_DESIGN_CANVAS).toEqual({ width: 1440, height: 810 })
    expect(WORKSTATION_SOURCE_CANVAS).toEqual({ width: 1448, height: 1086 })
    expect(WORKSTATION_RENDER_SIZE).toEqual({ width: 400, height: 300 })
    expect(WORKSTATION_SLOTS).toHaveLength(9)
  })

  it('matches the asset pack 3 × 3 slot coordinates exactly', () => {
    expect(
      WORKSTATION_SLOTS.map(({ stationRect }) => ({
        x: stationRect.x,
        y: stationRect.y,
      })),
    ).toEqual([
      { x: 70, y: 105 },
      { x: 520, y: 105 },
      { x: 970, y: 105 },
      { x: 70, y: 325 },
      { x: 520, y: 325 },
      { x: 970, y: 325 },
      { x: 70, y: 545 },
      { x: 520, y: 545 },
      { x: 970, y: 545 },
    ])
  })

  it('keeps relative labels and non-overlapping row hotspots in each slot', () => {
    for (const slot of WORKSTATION_SLOTS) {
      expect(slot.labelAnchor.x).toBe(WORKSTATION_RENDER_SIZE.width / 2)
      expect(slot.hotspot.x + slot.hotspot.width).toBeLessThanOrEqual(
        WORKSTATION_RENDER_SIZE.width,
      )
      expect(slot.hotspot.y + slot.hotspot.height).toBeLessThanOrEqual(220)
    }
  })

  it('fails closed for an unknown visual slot', () => {
    expect(() => getWorkstationSlot(10)).toThrow(
      'Unknown office workstation slot',
    )
  })
})
