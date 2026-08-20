import {
  BoxGeometry,
  CylinderGeometry,
  MeshStandardMaterial,
  PlaneGeometry,
  SphereGeometry,
  TorusGeometry,
} from 'three'
import { markRaw } from 'vue'

import type { OfficeSceneTheme } from '../theme/office-scene-theme'

export function createOfficeResources(theme: OfficeSceneTheme) {
  const geometries = {
    box: markRaw(new BoxGeometry(1, 1, 1)),
    sphere: markRaw(new SphereGeometry(0.5, 16, 12)),
    cylinder: markRaw(new CylinderGeometry(0.5, 0.5, 1, 12)),
    plane: markRaw(new PlaneGeometry(1, 1)),
    torus: markRaw(new TorusGeometry(0.5, 0.12, 8, 16)),
  }
  const materials = {
    floor: markRaw(
      new MeshStandardMaterial({ color: theme.floor, roughness: 0.95 }),
    ),
    wall: markRaw(
      new MeshStandardMaterial({ color: theme.wall, roughness: 0.9 }),
    ),
    desk: markRaw(
      new MeshStandardMaterial({ color: theme.desk, roughness: 0.78 }),
    ),
    chair: markRaw(
      new MeshStandardMaterial({ color: theme.chair, roughness: 0.82 }),
    ),
    monitor: markRaw(
      new MeshStandardMaterial({ color: theme.monitor, roughness: 0.56 }),
    ),
    plant: markRaw(
      new MeshStandardMaterial({ color: '#557963', roughness: 0.9 }),
    ),
    planter: markRaw(
      new MeshStandardMaterial({ color: '#8d7d6c', roughness: 0.92 }),
    ),
  }

  return {
    geometries,
    materials,
    update(nextTheme: OfficeSceneTheme) {
      materials.floor.color.set(nextTheme.floor)
      materials.wall.color.set(nextTheme.wall)
      materials.desk.color.set(nextTheme.desk)
      materials.chair.color.set(nextTheme.chair)
      materials.monitor.color.set(nextTheme.monitor)
    },
    dispose() {
      Object.values(geometries).forEach((geometry) => geometry.dispose())
      Object.values(materials).forEach((material) => material.dispose())
    },
  }
}

export type OfficeResources = ReturnType<typeof createOfficeResources>

export const OFFICE_RESOURCES_KEY = Symbol('device-office-resources')
