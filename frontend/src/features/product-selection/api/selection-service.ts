import type { ApiMode } from '@/shared/api'
import type { SelectionService } from '../model/contracts'

export const SELECTION_UNAVAILABLE = '选品能力尚未接入'
export async function createSelectionService(
  mode: ApiMode,
): Promise<SelectionService> {
  if (import.meta.env.VITE_API_MODE === 'mock' && mode === 'mock') {
    const { createSelectionMockHandlers } =
      await import('./selection-mock-handlers')
    return createSelectionMockHandlers()
  }
  // No proposed URL is sent before the Backend contract exists. Never fallback.
  const unavailable = async (): Promise<never> => {
    throw new Error(SELECTION_UNAVAILABLE)
  }
  return {
    available: false,
    previewPeriod: unavailable,
    categories: unavailable,
    strategies: unavailable,
    saveStrategy: unavailable,
    retrieve: unavailable,
    candidates: unavailable,
    candidate: unavailable,
    demoAction: unavailable,
    collectBatch: unavailable,
    updateCompassMetrics: unavailable,
    markCompetitor: unavailable,
  }
}
