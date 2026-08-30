import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  MOBILE_ICON_GALLERY_GROUPS,
  MOBILE_ICON_REGISTRY,
  MobileIcon,
  isMobileIconName,
  resolveMobileIcon,
} from '@/shared/icons'

describe('Mobile icon registry', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders primary Device and Task icons through the shared semantic entry', () => {
    for (const name of ['device', 'task'] as const) {
      const wrapper = mount(MobileIcon, {
        props: { name, tile: true },
      })

      expect(
        wrapper.get(`[data-icon-key="${name}"]`).attributes(),
      ).toMatchObject({
        'data-icon-role': 'primary',
        'aria-hidden': 'true',
      })
      expect(wrapper.find('svg.mobile-icon__glyph').exists()).toBe(true)
      expect(wrapper.classes()).toContain('mobile-icon--tile')
    }
  })

  it('reuses the monitor glyph for the DeviceCard and device detail', () => {
    for (const name of ['device', 'runtime-device'] as const) {
      const wrapper = mount(MobileIcon, { props: { name } })

      expect(wrapper.find('svg.mobile-icon__glyph').exists()).toBe(true)
      expect(resolveMobileIcon(name).source.kind).toBe('component')
    }
  })

  it('exposes a readable label only when an icon is not decorative', () => {
    const wrapper = mount(MobileIcon, {
      props: {
        name: 'online',
        decorative: false,
        label: '设备在线',
      },
    })

    expect(wrapper.attributes()).toMatchObject({
      role: 'img',
      'aria-label': '设备在线',
    })
    expect(wrapper.attributes('aria-hidden')).toBeUndefined()
  })

  it('allows shared consumers to override only size and semantic tone', () => {
    const wrapper = mount(MobileIcon, {
      props: {
        name: 'device',
        size: 24,
        tone: 'muted',
      },
    })

    expect(wrapper.classes()).toContain('mobile-icon--tone-muted')
    expect(wrapper.attributes('style')).toContain('font-size: 24px')
  })

  it('keeps gallery groups backed by registered semantic names', () => {
    for (const group of MOBILE_ICON_GALLERY_GROUPS) {
      for (const name of group.names) {
        expect(isMobileIconName(name)).toBe(true)
        expect(MOBILE_ICON_REGISTRY[name]).toBeDefined()
      }
    }
  })

  it('maps production surfaces to the intended icon role and semantic source', () => {
    const expectations = [
      ['device', 'primary', 'component'],
      ['task', 'primary', 'component'],
      ['runtime-device', 'runtime', 'component'],
      ['automation', 'runtime', 'vant'],
      ['application', 'capability', 'vant'],
      ['skill', 'capability', 'vant'],
      ['online', 'status', 'vant'],
      ['running', 'status', 'vant'],
      ['offline', 'status', 'vant'],
      ['device-nav', 'navigation', 'vant'],
      ['task-nav', 'navigation', 'vant'],
      ['theme-light', 'action', 'component'],
      ['theme-dark', 'action', 'component'],
      ['notification-bell', 'action', 'component'],
      ['filter', 'action', 'vant'],
      ['refresh', 'action', 'vant'],
      ['back', 'action', 'vant'],
      ['chevron-right', 'action', 'vant'],
    ] as const

    for (const [name, role, sourceKind] of expectations) {
      const definition = resolveMobileIcon(name)
      expect(definition.role).toBe(role)
      expect(definition.source.kind).toBe(sourceKind)
    }
  })

  it('falls back safely and reports an unregistered icon in development', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined)

    expect(resolveMobileIcon('not-a-mobile-icon')).toBe(
      MOBILE_ICON_REGISTRY.fallback,
    )
    expect(warn).toHaveBeenCalledWith(
      '[MobileIcon] 未注册图标：not-a-mobile-icon',
    )
  })
})
