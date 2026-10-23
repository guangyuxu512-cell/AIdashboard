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
    capabilities: {
      platformFilter: false,
      categoryFilter: false,
      edit: false,
      createGroup: false,
      moveGroup: false,
      remove: false,
      recollect: false,
      import: false,
      export: false,
      batchExport: false,
    },
    groups: reject,
    list: reject,
    detail: reject,
    saveEdit: reject,
    createGroup: reject,
    moveToGroup: reject,
    remove: reject,
    recollect: reject,
    exportSingle: reject,
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
  if (mode === 'real') {
    const { createProductLibraryRealService } =
      await import('./product-library-real')
    return createProductLibraryRealService()
  }
  return unavailable()
}
