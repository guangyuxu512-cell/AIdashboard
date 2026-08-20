import { describe, expect, it } from 'vitest'

import {
  getWorkstationSlot,
  OFFICE_DESIGN_CANVAS,
  WORKSTATION_SLOTS,
} from './office-layout'

describe('fixed device office layout', () => {
  it('defines nine unique slots on one 1440 × 810 design canvas', () => {
    expect(WORKSTATION_SLOTS).toHaveLength(9)
    expect(new Set(WORKSTATION_SLOTS.map((slot) => slot.slotId)).size).toBe(9)
    expect(OFFICE_DESIGN_CANVAS).toEqual({ width: 1440, height: 810 })
  })

  it('keeps every anchor and hotspot inside the fixed canvas', () => {
    for (const slot of WORKSTATION_SLOTS) {
      expect(slot.actorAnchor.x).toBeGreaterThanOrEqual(0)
      expect(slot.actorAnchor.y).toBeGreaterThanOrEqual(0)
      expect(slot.labelAnchor.x).toBeLessThanOrEqual(OFFICE_DESIGN_CANVAS.width)
      expect(slot.hotspot.x + slot.hotspot.width).toBeLessThanOrEqual(
        OFFICE_DESIGN_CANVAS.width,
      )
      expect(slot.hotspot.y + slot.hotspot.height).toBeLessThanOrEqual(
        OFFICE_DESIGN_CANVAS.height,
      )
    }
  })

  it('fails closed for an unknown visual slot', () => {
    expect(() => getWorkstationSlot(10)).toThrow(
      'Unknown office workstation slot',
    )
  })
})
