import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import type { Router } from 'vue-router'

const { warning, destroy } = vi.hoisted(() => ({
  warning: vi.fn(),
  destroy: vi.fn(),
}))
vi.mock('naive-ui', () => ({ useNotification: () => ({ warning }) }))

afterEach(() => {
  vi.resetModules()
  vi.clearAllMocks()
})

describe('client resource recovery', () => {
  it('marks load failures, keeps rejected navigation, and coalesces repeated errors', async () => {
    const {
      installClientUpdateDetection,
      clientUpdateRequired,
      isResourceLoadError,
    } = await import('./client-update')
    let onError: (error: unknown) => void = () => {}
    const remove = vi.fn()
    const stop = installClientUpdateDetection({
      onError: (handler: typeof onError) => {
        onError = handler
        return remove
      },
    } as unknown as Router)
    onError(new Error('API validation failed'))
    expect(clientUpdateRequired.value).toBe(false)
    const event = new Event('vite:preloadError', { cancelable: true })
    window.dispatchEvent(event)
    expect(clientUpdateRequired.value).toBe(true)
    expect(event.defaultPrevented).toBe(false)
    expect(
      isResourceLoadError(
        new Error(
          'Failed to fetch dynamically imported module: /assets/old.js',
        ),
      ),
    ).toBe(true)
    expect(
      isResourceLoadError(
        new Error('Unable to preload CSS for /assets/old.css'),
      ),
    ).toBe(true)
    stop()
    expect(remove).toHaveBeenCalledOnce()
  })

  it('preserves editing while showing a single notice and cancelling reload confirmation', async () => {
    warning.mockReturnValue({ destroy })
    const { installClientUpdateDetection } = await import('./client-update')
    const Notice = (await import('./ClientUpdateNotice.vue')).default
    const stop = installClientUpdateDetection({
      onError: () => () => {},
    } as unknown as Router)
    const wrapper = mount(
      defineComponent({
        components: { Notice },
        data: () => ({ draft: '未保存配置' }),
        template: '<input v-model="draft"><Notice />',
      }),
      {
        global: {
          stubs: {
            AppDialog: {
              props: ['show', 'negativeText'],
              emits: ['cancel'],
              template:
                '<div v-if="show"><slot /><button @click="$emit(\'cancel\')">{{negativeText}}</button></div>',
            },
          },
        },
      },
    )
    window.dispatchEvent(new Event('vite:preloadError'))
    window.dispatchEvent(new Event('vite:preloadError'))
    await nextTick()
    expect(warning).toHaveBeenCalledOnce()
    warning.mock.calls[0]![0].action().props.onClick()
    await nextTick()
    expect(wrapper.text()).toContain('重新加载会丢失尚未保存')
    await wrapper.get('button').trigger('click')
    expect(wrapper.find('button').exists()).toBe(false)
    expect(wrapper.get('input').element.value).toBe('未保存配置')
    // User can reopen the same notice instead of an auto-refresh/repeated popup.
    warning.mock.calls[0]![0].action().props.onClick()
    await nextTick()
    expect(wrapper.text()).toContain('继续编辑')
    wrapper.unmount()
    stop()
    expect(destroy).toHaveBeenCalledOnce()
  })
})
