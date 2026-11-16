import {
  configureDeviceDataSource,
  resetDeviceDataSource,
} from '@/entities/device'
import { configureTaskDataSource, resetTaskDataSource } from '@/entities/task'

export type MobileDataMode = 'real' | 'mock'

export function resolveMobileDataMode(
  isDevelopment: boolean,
  viteMode: string,
): MobileDataMode {
  return isDevelopment && viteMode === 'visual' ? 'mock' : 'real'
}

export const mobileDataMode = resolveMobileDataMode(
  import.meta.env.DEV,
  import.meta.env.MODE,
)

let configurationRevision = 0

export async function configureMobileDataSources(
  mode: MobileDataMode = mobileDataMode,
): Promise<void> {
  const revision = ++configurationRevision
  resetDeviceDataSource()
  resetTaskDataSource()
  if (!import.meta.env.DEV || mode !== 'mock') return

  const [{ visualMockDeviceDataSource }, { visualMockTaskDataSource }] =
    await Promise.all([
      import('@/entities/device/api/visual-mock-device-data-source'),
      import('@/entities/task/api/visual-mock-task-data-source'),
    ])

  if (revision !== configurationRevision) return

  configureDeviceDataSource(visualMockDeviceDataSource)
  configureTaskDataSource(visualMockTaskDataSource)
  console.info('[Mobile Visual Preview] Mock DataSource enabled')
}
