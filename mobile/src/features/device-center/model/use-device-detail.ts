import { computed, type MaybeRefOrGetter } from 'vue'

import {
  mapDeviceRead,
  useDeviceDetailQuery,
  useDeviceProviderInventoriesQuery,
  useDeviceSkillCapabilitiesQuery,
} from '@/entities/device'

import { useDeviceActiveTask } from './use-device-active-task'

export function useDeviceDetail(
  deviceId: MaybeRefOrGetter<string | undefined>,
) {
  const deviceQuery = useDeviceDetailQuery(deviceId)
  const hasDevice = computed(() => deviceQuery.data.value !== undefined)
  const auxiliaryEnabled = hasDevice
  const activeTask = useDeviceActiveTask(deviceId, auxiliaryEnabled)
  const providerQuery = useDeviceProviderInventoriesQuery(
    deviceId,
    auxiliaryEnabled,
  )
  const capabilityQuery = useDeviceSkillCapabilitiesQuery(
    deviceId,
    auxiliaryEnabled,
  )

  const providerHasData = computed(() => providerQuery.data.value !== undefined)
  const capabilityHasData = computed(
    () => capabilityQuery.data.value !== undefined,
  )

  return {
    device: computed(() =>
      deviceQuery.data.value
        ? mapDeviceRead(deviceQuery.data.value)
        : undefined,
    ),
    deviceQuery,
    isDeviceInitialLoading: computed(
      () => deviceQuery.isLoading.value && !hasDevice.value,
    ),
    isDeviceInitialError: computed(
      () => deviceQuery.isError.value && !hasDevice.value,
    ),
    isDeviceBackgroundError: computed(
      () => deviceQuery.isError.value && hasDevice.value,
    ),
    activeTask,
    provider: {
      query: providerQuery,
      isInitialLoading: computed(
        () => providerQuery.isLoading.value && !providerHasData.value,
      ),
      isInitialError: computed(
        () => providerQuery.isError.value && !providerHasData.value,
      ),
      isBackgroundError: computed(
        () => providerQuery.isError.value && providerHasData.value,
      ),
    },
    capability: {
      query: capabilityQuery,
      isInitialLoading: computed(
        () => capabilityQuery.isLoading.value && !capabilityHasData.value,
      ),
      isInitialError: computed(
        () => capabilityQuery.isError.value && !capabilityHasData.value,
      ),
      isBackgroundError: computed(
        () => capabilityQuery.isError.value && capabilityHasData.value,
      ),
    },
  }
}
