export interface ManagementLoginPollOptions {
  attemptId: string
  getStatus: (attemptId: string) => Promise<ManagementLoginStatusResult>
  // `true` keeps only the existing-shop failed-refresh window observable.
  // Main remains failed and performs no capture until an explicit reopen.
  onStatus: (
    status: ManagementLoginStatusResult,
  ) => void | boolean | Promise<void | boolean>
  onError: (error: unknown) => void
  intervalMs?: number
}

export function startManagementLoginPolling(
  options: ManagementLoginPollOptions,
): () => void {
  let timer: number | undefined
  let polling = false
  let stopped = false

  const poll = async (): Promise<void> => {
    if (polling || stopped) return
    polling = true
    try {
      const status = await options.getStatus(options.attemptId)
      if (stopped) return
      if (!status) throw new Error('登录状态读取失败')
      const keepWatching = (await options.onStatus(status)) === true
      if (
        status.status === 'closed' ||
        status.status === 'completed' ||
        (!keepWatching &&
          (status.status === 'identified' || status.status === 'failed'))
      ) {
        stop()
      }
    } catch (error) {
      if (stopped) return
      stop()
      options.onError(error)
    } finally {
      polling = false
    }
  }

  const stop = (): void => {
    stopped = true
    if (timer !== undefined) window.clearInterval(timer)
    timer = undefined
  }

  void poll()
  timer = window.setInterval(() => void poll(), options.intervalMs ?? 1500)
  return stop
}
