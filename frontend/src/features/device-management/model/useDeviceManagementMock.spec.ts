import { describe, expect, it } from 'vitest'

import { useDeviceManagementMock } from './useDeviceManagementMock'

describe('useDeviceManagementMock', () => {
  it('filters fixture devices only after query and resets them', () => {
    const management = useDeviceManagementMock()

    management.filterDraft.value.status = 'busy'
    expect(management.filteredDevices.value).toHaveLength(8)

    management.query()
    expect(management.filteredDevices.value).toHaveLength(2)
    expect(
      management.filteredDevices.value.every(
        (device) => device.status === 'busy',
      ),
    ).toBe(true)

    management.resetFilters()
    expect(management.filteredDevices.value).toHaveLength(8)
  })

  it('filters by available fixture capability', () => {
    const management = useDeviceManagementMock()
    management.filterDraft.value.capability = 'node'
    management.query()

    expect(management.filteredDevices.value).toHaveLength(4)
    expect(
      management.filteredDevices.value.every((device) =>
        device.capabilities.some(
          (capability) =>
            capability.capability === 'node' &&
            capability.availability === 'available',
        ),
      ),
    ).toBe(true)
  })
})
