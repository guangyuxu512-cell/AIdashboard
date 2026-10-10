import type { ApiMode } from '@/shared/api'
import type { SelectionService } from '../model/contracts'
import { createSelectionRealService } from './selection-real-service'

export const SELECTION_UNAVAILABLE = '选品能力尚未接入'
export async function createSelectionService(
  mode: ApiMode,
): Promise<SelectionService> {
  if (import.meta.env.VITE_API_MODE === 'mock' && mode === 'mock') {
    const { createSelectionMockHandlers } =
      await import('./selection-mock-handlers')
    return createSelectionMockHandlers()
  }
  // Only registered database read contracts are enabled; no guessed I/O URL.
  const unavailable = async (): Promise<never> => {
    throw new Error(SELECTION_UNAVAILABLE)
  }
  return createSelectionRealService(unavailable)
}
