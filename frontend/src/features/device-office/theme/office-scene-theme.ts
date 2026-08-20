import type { ResolvedTheme } from '@/stores/theme'

export interface OfficeSceneTheme {
  floor: string
  wall: string
  desk: string
  chair: string
  monitor: string
  ambientLight: string
  ambientLightIntensity: number
  mainLight: string
  mainLightIntensity: number
  accentLight: string
  accentLightIntensity: number
}

export const officeSceneTheme: Record<ResolvedTheme, OfficeSceneTheme> = {
  light: {
    floor: '#d9dde0',
    wall: '#eeeae2',
    desk: '#d8c5aa',
    chair: '#71808a',
    monitor: '#37444f',
    ambientLight: '#fff8ed',
    ambientLightIntensity: 1.9,
    mainLight: '#fff4dd',
    mainLightIntensity: 2.8,
    accentLight: '#b6d1cc',
    accentLightIntensity: 1.1,
  },
  dark: {
    floor: '#657887',
    wall: '#465463',
    desk: '#8a7b67',
    chair: '#647685',
    monitor: '#161d24',
    ambientLight: '#91a5ba',
    ambientLightIntensity: 2,
    mainLight: '#ffdba8',
    mainLightIntensity: 2.4,
    accentLight: '#7fa6a2',
    accentLightIntensity: 0.9,
  },
}

export function getOfficeSceneTheme(theme: ResolvedTheme): OfficeSceneTheme {
  return officeSceneTheme[theme]
}
