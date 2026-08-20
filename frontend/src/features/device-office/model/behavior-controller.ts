import type { DeviceActorState } from './types'
import type { OfficePoint } from './office-layout'

export interface OfficeWaypoint {
  id: 'workstation' | 'coffee'
  position: OfficePoint
}

export interface DeviceActorBehaviorPlan {
  states: readonly DeviceActorState[]
  waypoints: readonly OfficeWaypoint[]
}

export const IDLE_COFFEE_BEHAVIOR_CONTRACT: DeviceActorBehaviorPlan = {
  states: ['idle', 'walk', 'coffee', 'walk', 'idle'],
  waypoints: [
    { id: 'workstation', position: { x: 710, y: 505 } },
    { id: 'coffee', position: { x: 1245, y: 205 } },
  ],
}

// This file is only the future behavior boundary. It does not schedule or fake animation.
