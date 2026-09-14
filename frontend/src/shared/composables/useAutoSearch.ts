import { tryOnScopeDispose, useDebounceFn } from '@vueuse/core'

const activeCancels = new Set<() => void>()

/** Invalidate pending text searches before the authenticated actor changes. */
export function cancelAllAutoSearches(): void {
  activeCancels.forEach((cancel) => cancel())
}

export interface AutoSearchControls {
  onInput: (value?: string | null) => void
  onCompositionStart: () => void
  onCompositionEnd: (value?: string | null) => void
  onEnter: (event?: Pick<KeyboardEvent, 'isComposing'>) => void
  submitNow: () => void
  cancel: () => void
}

/** Explicit, IME-safe search submission for list filters. */
export function useAutoSearch(
  submit: () => void,
  delay = 300,
): AutoSearchControls {
  let generation = 0
  let composing = false

  const submitDebounced = useDebounceFn((scheduledGeneration: number) => {
    if (!composing && scheduledGeneration === generation) submit()
  }, delay)

  function cancel(): void {
    generation += 1
  }
  activeCancels.add(cancel)

  function submitNow(): void {
    cancel()
    submit()
  }

  function onInput(value?: string | null): void {
    cancel()
    if (composing) return
    if (value === '') {
      submit()
      return
    }
    void submitDebounced(generation)
  }

  function onCompositionStart(): void {
    composing = true
    cancel()
  }

  function onCompositionEnd(value?: string | null): void {
    composing = false
    onInput(value)
  }

  function onEnter(event?: Pick<KeyboardEvent, 'isComposing'>): void {
    if (composing || event?.isComposing) return
    submitNow()
  }

  tryOnScopeDispose(() => {
    cancel()
    activeCancels.delete(cancel)
  })

  return {
    onInput,
    onCompositionStart,
    onCompositionEnd,
    onEnter,
    submitNow,
    cancel,
  }
}
