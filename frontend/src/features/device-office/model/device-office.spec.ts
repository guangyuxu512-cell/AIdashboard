import { describe, expect, it } from 'vitest'

import { DEVICE_LIST_FIXTURE } from '@/entities/device'

import {
  createOfficeStations,
  getActorVariant,
  getDefaultLocalBehavior,
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

  it('derives a stable replaceable avatar variant from the device id', () => {
    expect(getActorVariant('device-stable-id')).toEqual(
      getActorVariant('device-stable-id'),
    )
    expect(getActorVariant('device-stable-id').index).toBeGreaterThanOrEqual(0)
  })

  it('keeps local presentation behavior subordinate to the visual state', () => {
    expect(getDefaultLocalBehavior('onlineIdle')).toBe('idle')
    expect(getDefaultLocalBehavior('busy')).toBe('work')
    expect(getDefaultLocalBehavior('offline')).toBe('sleep')
    expect(getDefaultLocalBehavior('error')).toBe('idle')
  })
})
