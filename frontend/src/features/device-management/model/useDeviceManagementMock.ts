import { computed, ref } from 'vue'

import {
  DEVICE_LIST_FIXTURE,
  type DeviceListItemViewModel,
} from '@/entities/device'

import type { DeviceFilterViewModel } from './types'

function createEmptyFilters(): DeviceFilterViewModel {
  return {
    status: null,
    tag: null,
    workerVersion: null,
    capability: null,
    keyword: '',
  }
}

function cloneFixtureRows(): DeviceListItemViewModel[] {
  return DEVICE_LIST_FIXTURE.map((device) => ({
    ...device,
    tags: [...device.tags],
    capabilities: device.capabilities.map((capability) => ({ ...capability })),
  }))
}

export function useDeviceManagementMock() {
  const devices = ref(cloneFixtureRows())
  const filterDraft = ref<DeviceFilterViewModel>(createEmptyFilters())
  const appliedFilters = ref<DeviceFilterViewModel>(createEmptyFilters())
  const page = ref(1)
  const pageSize = ref(10)
  const detailDevice = ref<DeviceListItemViewModel | null>(null)
  const detailVisible = ref(false)
  const addInfoVisible = ref(false)

  const filteredDevices = computed(() => {
    const filters = appliedFilters.value
    const keyword = filters.keyword.trim().toLocaleLowerCase()

    return devices.value.filter((device) => {
      const matchesKeyword =
        keyword.length === 0 ||
        [
          device.deviceName,
          device.location,
          device.systemDisplay,
          ...device.tags,
        ].some((value) => value.toLocaleLowerCase().includes(keyword))
      const matchesCapability =
        !filters.capability ||
        device.capabilities.some(
          (capability) =>
            capability.capability === filters.capability &&
            capability.availability === 'available',
        )

      return (
        matchesKeyword &&
        matchesCapability &&
        (!filters.status || device.status === filters.status) &&
        (!filters.tag || device.tags.includes(filters.tag)) &&
        (!filters.workerVersion ||
          device.workerVersionDisplay === filters.workerVersion)
      )
    })
  })

  const pagedDevices = computed(() => {
    const start = (page.value - 1) * pageSize.value
    return filteredDevices.value.slice(start, start + pageSize.value)
  })

  const statistics = computed(() => ({
    online: devices.value.filter((device) => device.status === 'online').length,
    offline: devices.value.filter((device) => device.status === 'offline')
      .length,
    busy: devices.value.filter((device) => device.status === 'busy').length,
    error: devices.value.filter((device) => device.status === 'error').length,
  }))

  function query(): void {
    appliedFilters.value = { ...filterDraft.value }
    page.value = 1
  }

  function resetFilters(): void {
    filterDraft.value = createEmptyFilters()
    appliedFilters.value = createEmptyFilters()
    page.value = 1
  }

  function openDetail(device: DeviceListItemViewModel): void {
    detailDevice.value = device
    detailVisible.value = true
  }

  function openAddInfo(): void {
    addInfoVisible.value = true
  }

  return {
    filterDraft,
    page,
    pageSize,
    detailDevice,
    detailVisible,
    addInfoVisible,
    filteredDevices,
    pagedDevices,
    statistics,
    query,
    resetFilters,
    openDetail,
    openAddInfo,
  }
}
