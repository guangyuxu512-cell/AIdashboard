import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { startManagementLoginPolling } from './management-login-poller'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (error: unknown) => void
  const promise = new Promise<T>((done, fail) => {
    resolve = done
    reject = fail
  })
  return { promise, resolve, reject }
}
function status(state: ManagementLoginStatusResult['status']) {
  return {
    attemptId: 'attempt',
    status: state,
    message: state,
  } as ManagementLoginStatusResult
}
beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

describe('management login terminal polling', () => {
  it('keeps one IPC while detection is pending and stops after its closed receipt', async () => {
    const pending = deferred<ManagementLoginStatusResult>()
    const getStatus = vi.fn(() => pending.promise)
    const onStatus = vi.fn(),
      onError = vi.fn()
    const stop = startManagementLoginPolling({
      attemptId: 'attempt',
      getStatus,
      onStatus,
      onError,
    })
    await vi.advanceTimersByTimeAsync(4500)
    expect(getStatus).toHaveBeenCalledTimes(1)
    pending.resolve(status('closed'))
    await vi.advanceTimersByTimeAsync(0)
    expect(onStatus).toHaveBeenCalledExactlyOnceWith(status('closed'))
    await vi.advanceTimersByTimeAsync(4500)
    expect(getStatus).toHaveBeenCalledTimes(1)
    expect(onError).not.toHaveBeenCalled()
    stop()
  })
  it.each(['identified', 'failed', 'completed'] as const)(
    'stops after the existing %s terminal status',
    async (state) => {
      const getStatus = vi.fn().mockResolvedValue(status(state))
      const onStatus = vi.fn(),
        onError = vi.fn()
      const stop = startManagementLoginPolling({
        attemptId: 'attempt',
        getStatus,
        onStatus,
        onError,
      })
      await vi.advanceTimersByTimeAsync(4500)
      expect(getStatus).toHaveBeenCalledTimes(1)
      expect(onStatus).toHaveBeenCalledTimes(1)
      expect(onError).not.toHaveBeenCalled()
      stop()
    },
  )
  it.each(['resolve', 'reject'] as const)(
    'ignores a late %s after cancellation',
    async (result) => {
      const pending = deferred<ManagementLoginStatusResult>()
      const onStatus = vi.fn(),
        onError = vi.fn()
      const stop = startManagementLoginPolling({
        attemptId: 'attempt',
        getStatus: () => pending.promise,
        onStatus,
        onError,
      })
      stop()
      if (result === 'resolve') pending.resolve(status('identified'))
      else pending.reject(new Error('isolated late status failure'))
      await vi.advanceTimersByTimeAsync(4500)
      expect(onStatus).not.toHaveBeenCalled()
      expect(onError).not.toHaveBeenCalled()
    },
  )
  it('reports a null bridge reply as an error, not a successful close, and stops polling', async () => {
    const getStatus = vi.fn().mockResolvedValue(null)
    const onStatus = vi.fn(),
      onError = vi.fn()
    const stop = startManagementLoginPolling({
      attemptId: 'attempt',
      getStatus,
      onStatus,
      onError,
    })
    await vi.advanceTimersByTimeAsync(4500)
    expect(getStatus).toHaveBeenCalledTimes(1)
    expect(onStatus).not.toHaveBeenCalled()
    expect(onError).toHaveBeenCalledTimes(1)
    stop()
  })
})
