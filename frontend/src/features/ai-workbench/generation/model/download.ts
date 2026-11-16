import type { AssetDownloadRequest } from '@/entities/asset'

import type {
  GenerationExecutionResultView,
  GenerationResultView,
} from './types'

/**
 * A result selection emitted by generation result views. The selection is
 * intentionally explicit: a single result must not be expanded by a parent
 * into its enclosing group or record.
 */
export type GenerationDownloadScope = 'SINGLE' | 'GROUP' | 'BATCH'

export type GenerationDownloadResult =
  GenerationExecutionResultView | GenerationResultView

export interface GenerationDownloadSelection {
  scope: GenerationDownloadScope
  results: readonly GenerationDownloadResult[]
}

function filenameFor(result: GenerationDownloadResult): string {
  if (result.name) return result.name
  return 'slotIndex' in result
    ? `generation-${result.slotIndex + 1}.png`
    : 'generation.png'
}

/**
 * Keep every generation surface on the formal Asset content URL path. A
 * thumbnail URL never enters the download queue.
 */
export function toGenerationAssetDownloadRequests(
  results: readonly GenerationDownloadResult[],
): AssetDownloadRequest[] {
  return results.flatMap((result) =>
    result.status === 'SUCCESS' && result.previewUrl
      ? [
          {
            id: result.id,
            contentUrl: result.previewUrl,
            filename: filenameFor(result),
          },
        ]
      : [],
  )
}
