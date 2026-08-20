import { beforeEach, describe, expect, it } from 'vitest'

import {
  DEVICE_OFFICE_VIEW_STORAGE_KEY,
  readDeviceCenterViewMode,
} from './useDeviceOfficeView'

describe('device office view preference', () => {
  beforeEach(() => window.localStorage.clear())

  it('defaults to office and restores a valid list preference', () => {
    expect(readDeviceCenterViewMode()).toBe('office')
    window.localStorage.setItem(DEVICE_OFFICE_VIEW_STORAGE_KEY, 'list')
    expect(readDeviceCenterViewMode()).toBe('list')
  })

  it('ignores unknown persisted values', () => {
    window.localStorage.setItem(DEVICE_OFFICE_VIEW_STORAGE_KEY, 'unknown')
    expect(readDeviceCenterViewMode()).toBe('office')
  })
})
