import { ref, watch } from 'vue'

import type { DeviceCenterViewMode } from './types'

export const DEVICE_OFFICE_VIEW_STORAGE_KEY = 'control-center.device-view-mode'

function isDeviceCenterViewMode(value: string | null): value is DeviceCenterViewMode {
  return value === 'office' || value === 'list'
}

export function readDeviceCenterViewMode(): DeviceCenterViewMode {
  if (typeof window === 'undefined') return 'office'
  try {
    const value = window.localStorage.getItem(DEVICE_OFFICE_VIEW_STORAGE_KEY)
    return isDeviceCenterViewMode(value) ? value : 'office'
  } catch {
    return 'office'
  }
}

export function useDeviceOfficeView() {
  const viewMode = ref<DeviceCenterViewMode>(readDeviceCenterViewMode())
  watch(viewMode, (value) => {
    try {
      window.localStorage.setItem(DEVICE_OFFICE_VIEW_STORAGE_KEY, value)
    } catch {
      // The selected view remains usable when storage is unavailable.
    }
  })
  return { viewMode }
}
