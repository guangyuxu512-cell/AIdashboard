export interface ManagementLoginPollOptions {
  attemptId: string
  getStatus: (attemptId: string) => Promise<ManagementLoginStatusResult>
  onStatus: (status: ManagementLoginStatusResult) => void | Promise<void>
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
      await options.onStatus(status)
      if (
        status.status === 'identified' ||
        status.status === 'closed' ||
        status.status === 'failed' ||
        status.status === 'completed'
      ) {
        stop()
      }
    } catch (error) {
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
