import type { ResolvedTheme } from '@/stores/theme'

import type { DeviceVisualState } from '../model/types'

const ASSET_ROOT = '/assets/device-office'

export interface OfficeThemeLayerAssets {
  background: string
  foreground: string
}

export const officeThemeLayerAssets: Record<
  ResolvedTheme,
  OfficeThemeLayerAssets
> = {
  light: {
    background: `${ASSET_ROOT}/light/background.svg`,
    foreground: `${ASSET_ROOT}/light/foreground.svg`,
  },
  dark: {
    background: `${ASSET_ROOT}/dark/background.svg`,
    foreground: `${ASSET_ROOT}/dark/foreground.svg`,
  },
}

export const officeActorAssets: Record<DeviceVisualState, string> = {
  empty: `${ASSET_ROOT}/actors/empty/placeholder.svg`,
  onlineIdle: `${ASSET_ROOT}/actors/online-idle/placeholder.svg`,
  busy: `${ASSET_ROOT}/actors/busy/placeholder.svg`,
  offline: `${ASSET_ROOT}/actors/offline/placeholder.svg`,
  error: `${ASSET_ROOT}/actors/error/placeholder.svg`,
}

export const officeScreenAssets: Record<DeviceVisualState, string> = {
  empty: `${ASSET_ROOT}/screens/idle/placeholder.svg`,
  onlineIdle: `${ASSET_ROOT}/screens/idle/placeholder.svg`,
  busy: `${ASSET_ROOT}/screens/busy/placeholder.svg`,
  offline: `${ASSET_ROOT}/screens/offline/placeholder.svg`,
  error: `${ASSET_ROOT}/screens/error/placeholder.svg`,
}
