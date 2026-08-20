import { describe, expect, it } from 'vitest'

import { DEVICE_LIST_FIXTURE } from '@/entities/device'

import {
  createOfficeStations,
  getActorVariant,
  mapDeviceVisualState,
  mapVisualStateToActorState,
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
    expect(
      stations.slice(4).every((station) => station.visualState === 'empty'),
    ).toBe(true)
  })

  it('never binds more than nine devices to one office page', () => {
    const devices = [...DEVICE_LIST_FIXTURE, ...DEVICE_LIST_FIXTURE]
    expect(
      createOfficeStations(devices).filter((station) => station.device),
    ).toHaveLength(OFFICE_PAGE_SIZE)
  })

  it('derives a stable replaceable avatar variant from the device id', () => {
    expect(getActorVariant('device-stable-id')).toEqual(
      getActorVariant('device-stable-id'),
    )
    expect(['blue', 'green', 'purple', 'orange']).toContain(
      getActorVariant('device-stable-id').accentVariant,
    )
  })

  it('maps visual state to an asset-facing actor state', () => {
    expect(mapVisualStateToActorState('onlineIdle')).toBe('idle')
    expect(mapVisualStateToActorState('busy')).toBe('work')
    expect(mapVisualStateToActorState('offline')).toBe('sleep')
    expect(mapVisualStateToActorState('error')).toBe('error')
  })
})
