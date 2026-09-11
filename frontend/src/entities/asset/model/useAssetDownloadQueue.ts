import { computed, ref } from 'vue'

import { ApiError, toApiError } from '@/shared/api'

import { fetchAssetDownload } from '../api/asset-api'

const defaultConcurrency = 3

export interface AssetDownloadRequest {
  id: string
  contentUrl: string
  filename: string
}

export interface AssetDownloadFailure {
  request: AssetDownloadRequest
  code: string
  requestId: string | null
  message: string
}

export interface AssetDownloadResult {
  request: AssetDownloadRequest
  status: 'SUCCESS' | 'FAILED' | 'CANCELLED'
  failure?: AssetDownloadFailure
}

export interface AssetDownloadSummary {
  results: AssetDownloadResult[]
  succeeded: number
  failed: number
  cancelled: number
}

export interface AssetDownloadQueueOptions {
  concurrency?: number
}

function triggerBrowserDownload(blob: Blob, filename: string): void {
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0)
}

function normalizeRequests(
  requests: readonly AssetDownloadRequest[],
): AssetDownloadRequest[] {
  const unique = new Map<string, AssetDownloadRequest>()
  for (const request of requests) {
    if (!unique.has(request.id)) unique.set(request.id, request)
  }
  return [...unique.values()]
}

function downloadFailure(
  request: AssetDownloadRequest,
  error: unknown,
): AssetDownloadFailure {
  const apiError = toApiError(error)
  return {
    request,
    code: apiError.code,
    requestId: apiError.requestId,
    message: apiError.message,
  }
}

export function formatAssetDownloadFailure(failure: AssetDownloadFailure): string {
  const requestId = failure.requestId ? `（请求编号：${failure.requestId}）` : ''
  return `${failure.request.filename} 下载失败：${failure.message}${requestId}`
}

export function useAssetDownloadQueue(options: AssetDownloadQueueOptions = {}) {
  const concurrency = Math.max(1, options.concurrency ?? defaultConcurrency)
  const isDownloading = ref(false)
  const totalCount = ref(0)
  const completedCount = ref(0)
  const loadedBytes = ref(0)
  const totalBytes = ref<number | null>(null)
  const failedRequests = ref<AssetDownloadRequest[]>([])
  let activeController: AbortController | null = null

  const progressLabel = computed(() => {
    if (!totalCount.value) return '0 / 0'
    return `${completedCount.value} / ${totalCount.value}`
  })

  function cancel(): void {
    activeController?.abort()
  }

  async function start(
    requested: readonly AssetDownloadRequest[],
  ): Promise<AssetDownloadSummary | null> {
    if (isDownloading.value) return null

    const requests = normalizeRequests(requested)
    if (!requests.length) {
      failedRequests.value = []
      return { results: [], succeeded: 0, failed: 0, cancelled: 0 }
    }

    const controller = new AbortController()
    const byteProgress = new Map<string, { loaded: number; total: number | null }>()
    const results: AssetDownloadResult[] = []
    let nextIndex = 0
    activeController = controller
    isDownloading.value = true
    totalCount.value = requests.length
    completedCount.value = 0
    loadedBytes.value = 0
    totalBytes.value = null
    failedRequests.value = []

    const refreshProgress = (): void => {
      loadedBytes.value = [...byteProgress.values()].reduce(
        (sum, item) => sum + item.loaded,
        0,
      )
      const totals = [...byteProgress.values()].map((item) => item.total)
      totalBytes.value = totals.every((total) => total !== null)
        ? totals.reduce((sum, total) => sum + (total ?? 0), 0)
        : null
    }

    const consume = async (): Promise<void> => {
      while (true) {
        if (controller.signal.aborted) return
        const index = nextIndex
        nextIndex += 1
        const request = requests[index]
        if (!request) return
        try {
          const blob = await fetchAssetDownload(request.contentUrl, {
            signal: controller.signal,
            onProgress: (progress) => {
              byteProgress.set(request.id, {
                loaded: progress.loadedBytes,
                total: progress.totalBytes,
              })
              refreshProgress()
            },
          })
          triggerBrowserDownload(blob, request.filename)
          results.push({ request, status: 'SUCCESS' })
        } catch (error) {
          const failure = downloadFailure(request, error)
          results.push({
            request,
            status:
              failure.code === 'REQUEST_CANCELLED' ? 'CANCELLED' : 'FAILED',
            failure,
          })
        } finally {
          completedCount.value += 1
        }
      }
    }

    try {
      await Promise.all(
        Array.from({ length: Math.min(concurrency, requests.length) }, consume),
      )
    } finally {
      if (activeController === controller) activeController = null
      isDownloading.value = false
    }

    failedRequests.value = results
      .filter((result) => result.status === 'FAILED')
      .map((result) => result.request)
    const summary = {
      results,
      succeeded: results.filter((result) => result.status === 'SUCCESS').length,
      failed: results.filter((result) => result.status === 'FAILED').length,
      cancelled: results.filter((result) => result.status === 'CANCELLED').length,
    }
    return summary
  }

  async function retryFailed(): Promise<AssetDownloadSummary | null> {
    return start(failedRequests.value)
  }

  return {
    isDownloading,
    totalCount,
    completedCount,
    loadedBytes,
    totalBytes,
    progressLabel,
    failedRequests,
    cancel,
    start,
    retryFailed,
  }
}

export function isAssetDownloadCancelled(error: unknown): boolean {
  return error instanceof ApiError && error.code === 'REQUEST_CANCELLED'
}
