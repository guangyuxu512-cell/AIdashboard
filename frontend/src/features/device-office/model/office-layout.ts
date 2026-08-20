export const OFFICE_DESIGN_CANVAS = {
  width: 1440,
  height: 810,
} as const

export const WORKSTATION_SOURCE_CANVAS = {
  width: 1448,
  height: 1086,
} as const

export const WORKSTATION_RENDER_SIZE = {
  width: 400,
  height: 300,
} as const

export interface OfficePoint {
  x: number
  y: number
}

export interface OfficeRect extends OfficePoint {
  width: number
  height: number
}

export interface WorkstationSlot {
  slotId: number
  stationRect: OfficeRect
  labelAnchor: OfficePoint
  hotspot: OfficeRect
  zIndex: number
}

const SLOT_POSITIONS = [
  { x: 70, y: 105 },
  { x: 520, y: 105 },
  { x: 970, y: 105 },
  { x: 70, y: 325 },
  { x: 520, y: 325 },
  { x: 970, y: 325 },
  { x: 70, y: 545 },
  { x: 520, y: 545 },
  { x: 970, y: 545 },
] as const

export const WORKSTATION_SLOTS: readonly WorkstationSlot[] = SLOT_POSITIONS.map(
  (position, index) => ({
    slotId: index + 1,
    stationRect: {
      ...position,
      ...WORKSTATION_RENDER_SIZE,
    },
    labelAnchor: { x: WORKSTATION_RENDER_SIZE.width / 2, y: 14 },
    hotspot: { x: 38, y: 28, width: 324, height: 186 },
    zIndex: 10 + Math.floor(index / 3) * 10 + (index % 3),
  }),
)

export const WORKSTATION_FX_LAYOUT = {
  offline: { x: 284, y: 24, width: 78, height: 45 },
  error: { x: 294, y: 42, width: 58, height: 58 },
} as const satisfies Record<'offline' | 'error', OfficeRect>

export function getWorkstationSlot(slotId: number): WorkstationSlot {
  const slot = WORKSTATION_SLOTS.find(
    (candidate) => candidate.slotId === slotId,
  )
  if (!slot) throw new Error(`Unknown office workstation slot: ${slotId}`)
  return slot
}
