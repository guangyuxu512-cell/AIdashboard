import { describe, expect, it } from 'vitest'

import { DEVICE_LIST_FIXTURE } from '@/entities/device'

import {
  createOfficeStations,
  getMascotVariant,
  mapDeviceVisualState,
  OFFICE_PAGE_SIZE,
} from './device-office'

describe('device office view model', () => {
  it('maps backend runtime states without changing the backend contract', () => {
    expect(mapDeviceVisualState('online')).toBe('onlineIdle')
    expect(mapDeviceVisualState('busy')).toBe('busy')
    expect(mapDeviceVisualState('offline')).toBe('offline')
    expect(mapDeviceVisualState('unavailable')).toBe('offline')
    expect(mapDeviceVisualState('error')).toBe('error')
  })

  it('always creates nine stations and fills missing devices with empty slots', () => {
    const stations = createOfficeStations(DEVICE_LIST_FIXTURE.slice(0, 4))
    expect(stations).toHaveLength(OFFICE_PAGE_SIZE)
    expect(stations.filter((station) => station.device)).toHaveLength(4)
    expect(stations.slice(4).every((station) => station.visualState === 'empty')).toBe(
      true,
    )
  })

  it('never binds more than nine devices to one office page', () => {
    const devices = [...DEVICE_LIST_FIXTURE, ...DEVICE_LIST_FIXTURE]
    expect(createOfficeStations(devices).filter((station) => station.device)).toHaveLength(
      OFFICE_PAGE_SIZE,
    )
  })

  it('derives a stable mascot variant from the device id', () => {
    expect(getMascotVariant('device-stable-id')).toEqual(
      getMascotVariant('device-stable-id'),
    )
    expect(getMascotVariant('device-stable-id').index).toBeGreaterThanOrEqual(0)
  })
})
