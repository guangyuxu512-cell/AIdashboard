import { effectScope } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { cancelAllAutoSearches, useAutoSearch } from './useAutoSearch'

afterEach(() => {
  vi.useRealTimers()
})

describe('useAutoSearch', () => {
  it('submits the latest text after 300ms', async () => {
    vi.useFakeTimers()
    const submit = vi.fn()
    const controls = useAutoSearch(submit)

    controls.onInput('参')
    controls.onInput('参数')
    await vi.advanceTimersByTimeAsync(299)
    expect(submit).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    expect(submit).toHaveBeenCalledTimes(1)
  })

  it('waits for IME composition and submits confirmed text once', async () => {
    vi.useFakeTimers()
    const submit = vi.fn()
    const controls = useAutoSearch(submit)

    controls.onCompositionStart()
    controls.onInput('can')
    await vi.advanceTimersByTimeAsync(500)
    expect(submit).not.toHaveBeenCalled()
    controls.onCompositionEnd('参数')
    await vi.advanceTimersByTimeAsync(300)
    expect(submit).toHaveBeenCalledTimes(1)
  })

  it('submits Enter and clear immediately without a later duplicate', async () => {
    vi.useFakeTimers()
    const submit = vi.fn()
    const controls = useAutoSearch(submit)

    controls.onInput('配置')
    controls.onEnter({ isComposing: false })
    expect(submit).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(500)
    expect(submit).toHaveBeenCalledTimes(1)
    controls.onInput('')
    expect(submit).toHaveBeenCalledTimes(2)
  })

  it('invalidates pending work when its scope is disposed', async () => {
    vi.useFakeTimers()
    const submit = vi.fn()
    const scope = effectScope()
    const controls = scope.run(() => useAutoSearch(submit))!
    controls.onInput('离开页面')
    scope.stop()

    await vi.advanceTimersByTimeAsync(500)
    expect(submit).not.toHaveBeenCalled()
  })

  it('invalidates pending work before the actor context changes', async () => {
    vi.useFakeTimers()
    const submit = vi.fn()
    const controls = useAutoSearch(submit)
    controls.onInput('旧团队条件')

    cancelAllAutoSearches()
    await vi.advanceTimersByTimeAsync(500)

    expect(submit).not.toHaveBeenCalled()
  })
})
