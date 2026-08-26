import { computed, type MaybeRefOrGetter } from 'vue'

import {
  mapDeviceRead,
  useDeviceDetailQuery,
  useDeviceProviderInventoriesQuery,
  useDeviceSkillCapabilitiesQuery,
} from '@/entities/device'

import { useDeviceActiveTask } from './use-device-active-task'

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback
}

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
    deviceErrorMessage: computed(() =>
      errorMessage(deviceQuery.error.value, '设备详情加载失败'),
    ),
    isDeviceInitialLoading: computed(
      () => deviceQuery.isPending.value && !hasDevice.value,
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
      errorMessage: computed(() =>
        errorMessage(providerQuery.error.value, '影刀快照加载失败'),
      ),
      isInitialLoading: computed(
        () => providerQuery.isPending.value && !providerHasData.value,
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
      errorMessage: computed(() =>
        errorMessage(capabilityQuery.error.value, '技能能力加载失败'),
      ),
      isInitialLoading: computed(
        () => capabilityQuery.isPending.value && !capabilityHasData.value,
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
