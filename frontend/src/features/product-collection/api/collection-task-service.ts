import type { ApiMode } from '@/shared/api'
import type { CollectionTaskService } from '../model/contracts'

export const COLLECTION_TASKS_UNAVAILABLE = '商品资料采集尚未接入正式服务'

function unavailable(): CollectionTaskService {
  const reject = async (): Promise<never> => {
    throw new Error(COLLECTION_TASKS_UNAVAILABLE)
  }
  return {
    available: false,
    mode: 'real',
    list: reject,
    detail: reject,
    create: reject,
    retry: reject,
    cancel: reject,
  }
}

export async function createCollectionTaskService(
  mode: ApiMode,
): Promise<CollectionTaskService> {
  if (import.meta.env.VITE_API_MODE === 'mock' && mode === 'mock') {
    const { createCollectionTaskMockService } =
      await import('./collection-task-mock-store')
    return createCollectionTaskMockService()
  }
  return unavailable()
}
