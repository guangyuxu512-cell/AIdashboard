export const OFFICE_DESIGN_CANVAS = {
  width: 1440,
  height: 810,
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
  actorAnchor: OfficePoint
  actorScale: number
  screenRect: OfficeRect
  labelAnchor: OfficePoint
  hotspot: OfficeRect
  zIndex: number
}

export const WORKSTATION_SLOTS: readonly WorkstationSlot[] = [
  {
    slotId: 1,
    actorAnchor: { x: 365, y: 322 },
    actorScale: 1,
    screenRect: { x: 430, y: 250, width: 92, height: 56 },
    labelAnchor: { x: 370, y: 190 },
    hotspot: { x: 250, y: 185, width: 275, height: 190 },
    zIndex: 10,
  },
  {
    slotId: 2,
    actorAnchor: { x: 710, y: 318 },
    actorScale: 1,
    screenRect: { x: 735, y: 240, width: 108, height: 62 },
    labelAnchor: { x: 710, y: 184 },
    hotspot: { x: 570, y: 180, width: 285, height: 195 },
    zIndex: 11,
  },
  {
    slotId: 3,
    actorAnchor: { x: 1082, y: 320 },
    actorScale: 1,
    screenRect: { x: 1010, y: 242, width: 96, height: 58 },
    labelAnchor: { x: 1060, y: 190 },
    hotspot: { x: 930, y: 185, width: 275, height: 190 },
    zIndex: 12,
  },
  {
    slotId: 4,
    actorAnchor: { x: 370, y: 503 },
    actorScale: 1,
    screenRect: { x: 410, y: 427, width: 98, height: 58 },
    labelAnchor: { x: 375, y: 373 },
    hotspot: { x: 250, y: 365, width: 275, height: 190 },
    zIndex: 20,
  },
  {
    slotId: 5,
    actorAnchor: { x: 710, y: 505 },
    actorScale: 1,
    screenRect: { x: 715, y: 425, width: 105, height: 60 },
    labelAnchor: { x: 710, y: 371 },
    hotspot: { x: 570, y: 365, width: 285, height: 195 },
    zIndex: 21,
  },
  {
    slotId: 6,
    actorAnchor: { x: 1080, y: 505 },
    actorScale: 1,
    screenRect: { x: 1010, y: 425, width: 98, height: 60 },
    labelAnchor: { x: 1065, y: 373 },
    hotspot: { x: 930, y: 365, width: 275, height: 195 },
    zIndex: 22,
  },
  {
    slotId: 7,
    actorAnchor: { x: 370, y: 690 },
    actorScale: 1,
    screenRect: { x: 410, y: 610, width: 98, height: 58 },
    labelAnchor: { x: 375, y: 555 },
    hotspot: { x: 250, y: 548, width: 275, height: 190 },
    zIndex: 30,
  },
  {
    slotId: 8,
    actorAnchor: { x: 710, y: 690 },
    actorScale: 1,
    screenRect: { x: 715, y: 610, width: 98, height: 58 },
    labelAnchor: { x: 710, y: 555 },
    hotspot: { x: 570, y: 548, width: 285, height: 190 },
    zIndex: 31,
  },
  {
    slotId: 9,
    actorAnchor: { x: 1080, y: 690 },
    actorScale: 1,
    screenRect: { x: 1010, y: 610, width: 98, height: 58 },
    labelAnchor: { x: 1065, y: 555 },
    hotspot: { x: 930, y: 548, width: 275, height: 190 },
    zIndex: 32,
  },
]

export function getWorkstationSlot(slotId: number): WorkstationSlot {
  const slot = WORKSTATION_SLOTS.find(
    (candidate) => candidate.slotId === slotId,
  )
  if (!slot) throw new Error(`Unknown office workstation slot: ${slotId}`)
  return slot
}
