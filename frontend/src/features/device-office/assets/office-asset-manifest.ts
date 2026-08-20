export const OFFICE_ASSET_KEYS = [
  'mascot',
  'desk',
  'chair',
  'monitor',
  'officeProps',
] as const

export type OfficeAssetKey = (typeof OFFICE_ASSET_KEYS)[number]

export const OFFICE_AVATAR_ANIMATION_CLIPS = [
  'Idle',
  'Walk',
  'SitWork',
  'Sleep',
  'CoffeeIdle',
] as const

export type OfficeAvatarAnimationClip =
  (typeof OFFICE_AVATAR_ANIMATION_CLIPS)[number]

export interface OfficeAssetDefinition {
  key: OfficeAssetKey
  url: string
  requiredNodes: readonly string[]
  requiredAnimations: readonly OfficeAvatarAnimationClip[]
}

export const officeAssetManifest: Record<OfficeAssetKey, OfficeAssetDefinition> = {
  mascot: {
    key: 'mascot',
    url: '/assets/device-office/mascot.glb',
    requiredNodes: ['AvatarRoot', 'Accent', 'AccessoryHeadset', 'AccessoryScarf', 'AccessoryBadge'],
    requiredAnimations: OFFICE_AVATAR_ANIMATION_CLIPS,
  },
  desk: {
    key: 'desk',
    url: '/assets/device-office/desk.glb',
    requiredNodes: ['DeskRoot'],
    requiredAnimations: [],
  },
  chair: {
    key: 'chair',
    url: '/assets/device-office/chair.glb',
    requiredNodes: ['ChairRoot'],
    requiredAnimations: [],
  },
  monitor: {
    key: 'monitor',
    url: '/assets/device-office/monitor.glb',
    requiredNodes: ['MonitorRoot', 'Screen'],
    requiredAnimations: [],
  },
  officeProps: {
    key: 'officeProps',
    url: '/assets/device-office/office-props.glb',
    requiredNodes: ['OfficeRoot', 'CoffeeBar', 'OverviewScreen'],
    requiredAnimations: [],
  },
}

