export const DEVICE_ARTWORK_KINDS = ['desktop', 'laptop', 'server'] as const

export type DeviceArtworkKind = (typeof DEVICE_ARTWORK_KINDS)[number]

export const DEVICE_ARTWORK_STATES = ['online', 'running', 'offline'] as const

export type DeviceArtworkState = (typeof DEVICE_ARTWORK_STATES)[number]
