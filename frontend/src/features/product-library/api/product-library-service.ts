import type { ApiMode } from '@/shared/api'
import type { ProductLibraryService } from '../model/contracts'

export const PRODUCT_LIBRARY_UNAVAILABLE = '商品库正式服务尚未接入'

function unavailable(): ProductLibraryService {
  const reject = async (): Promise<never> => {
    throw new Error(PRODUCT_LIBRARY_UNAVAILABLE)
  }
  return {
    available: false,
    mode: 'real',
    groups: reject,
    list: reject,
    detail: reject,
    createGroup: reject,
    moveToGroup: reject,
    remove: reject,
    recollect: reject,
  }
}

export async function createProductLibraryService(
  mode: ApiMode,
): Promise<ProductLibraryService> {
  if (import.meta.env.VITE_API_MODE === 'mock' && mode === 'mock') {
    const { createProductLibraryMockService } =
      await import('./product-library-mock-store')
    return createProductLibraryMockService()
  }
  return unavailable()
}
