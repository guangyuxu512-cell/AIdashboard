import { afterEach, describe, expect, it } from 'vitest'

import {
  VISUAL_APPEARANCE_TUNER_STORAGE_KEY,
  VISUAL_TOKEN_TUNER_STORAGE_KEY,
  createVisualAppearanceTunerRuntime,
  createVisualTokenTunerRuntime,
  findVisualAppearanceTokenDefinition,
  findVisualTokenDefinition,
  type VisualAppearanceTokenDefinition,
  type VisualTokenStorage,
  visualAppearanceTokenRegistry,
} from '@/dev/visual-token-tuner'

class MemoryStorage implements VisualTokenStorage {
  readonly values = new Map<string, string>()

  getItem(key: string): string | null {
    return this.values.get(key) ?? null
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value)
  }

  removeItem(key: string): void {
    this.values.delete(key)
  }
}

function getAppearanceDefinition(key: string): VisualAppearanceTokenDefinition {
  const definition = findVisualAppearanceTokenDefinition(key)
  if (!definition) throw new Error(`缺少外观测试 Token：${key}`)
  return definition
}

function createComputedStyle(
  root: HTMLElement,
): (element: Element) => CSSStyleDeclaration {
  return (element) => {
    if (element !== root) throw new Error('调参器读取了非根元素样式')
    return {
      getPropertyValue: (cssVar: string) => {
        const inlineValue = root.style.getPropertyValue(cssVar)
        if (inlineValue) return inlineValue
        return (
          visualAppearanceTokenRegistry
            .find((definition) => definition.cssVar === cssVar)
            ?.defaultValue.toString() ?? ''
        )
      },
    } as CSSStyleDeclaration
  }
}

afterEach(() => {
  document
    .getElementById(
      'control-center-mobile-visual-token-tuner-appearance-overrides',
    )
    ?.remove()
  document.documentElement.removeAttribute('data-theme')
})

describe('Visual Token Tuner V3 appearance runtime', () => {
  it('只登记 Stage 3B 外观角色，不把 Stage 2 几何重新暴露为外观参数', () => {
    expect(
      visualAppearanceTokenRegistry.map((definition) => definition.key),
    ).toEqual(
      expect.arrayContaining([
        'radius-card',
        'radius-panel',
        'radius-control',
        'radius-tag',
        'radius-overlay',
        'border-surface-width',
        'border-control-width',
        'border-overlay-width',
        'light-shadow-card-blur',
        'dark-shadow-overlay-opacity',
      ]),
    )
    expect(
      visualAppearanceTokenRegistry.some((definition) =>
        definition.cssVar.startsWith('--layout-'),
      ),
    ).toBe(false)
    expect(
      visualAppearanceTokenRegistry.some((definition) =>
        [
          '--bg-',
          '--text-',
          '--color-',
          '--status-',
          '--border-default',
          '--border-divider',
          '--border-subtle',
        ].some((prefix) => definition.cssVar.startsWith(prefix)),
      ),
    ).toBe(false)
  })

  it('使用独立 V3 存储、实时覆盖并在刷新后恢复', () => {
    const storage = new MemoryStorage()
    const cardRadius = getAppearanceDefinition('radius-card')
    const firstRoot = document.createElement('html')
    const firstRuntime = createVisualAppearanceTunerRuntime({
      enabled: true,
      root: firstRoot,
      storage,
      getComputedStyle: createComputedStyle(firstRoot),
      getBaseline: (definition) => definition.defaultValue,
    })

    firstRuntime.setValue(cardRadius, 22)
    expect(firstRoot.style.getPropertyValue('--radius-card')).toBe('22px')
    expect(storage.values.get(VISUAL_APPEARANCE_TUNER_STORAGE_KEY)).toContain(
      '"--radius-card":"22px"',
    )
    expect(storage.values.has(VISUAL_TOKEN_TUNER_STORAGE_KEY)).toBe(false)

    const refreshedRoot = document.createElement('html')
    const refreshedRuntime = createVisualAppearanceTunerRuntime({
      enabled: true,
      root: refreshedRoot,
      storage,
      getComputedStyle: createComputedStyle(refreshedRoot),
      getBaseline: (definition) => definition.defaultValue,
    })
    refreshedRuntime.restore()

    expect(refreshedRoot.style.getPropertyValue('--radius-card')).toBe('22px')
    expect(refreshedRuntime.readValue(cardRadius)).toBe(22)
  })

  it('按主题隔离阴影，恢复一个阴影主题不会清除另一个主题', () => {
    const storage = new MemoryStorage()
    const root = document.documentElement
    const lightCardOpacity = getAppearanceDefinition(
      'light-shadow-card-opacity',
    )
    const darkCardOpacity = getAppearanceDefinition('dark-shadow-card-opacity')
    const runtime = createVisualAppearanceTunerRuntime({
      enabled: true,
      root,
      storage,
      document,
      getBaseline: (definition) => definition.defaultValue,
    })

    runtime.setValue(lightCardOpacity, 12)
    runtime.setValue(darkCardOpacity, 30)
    const style = document.getElementById(
      'control-center-mobile-visual-token-tuner-appearance-overrides',
    )
    expect(style?.textContent).toContain(":root[data-theme='light']")
    expect(style?.textContent).toContain('--shadow-card-opacity: 12%;')
    expect(style?.textContent).toContain(":root[data-theme='dark']")
    expect(style?.textContent).toContain('--shadow-card-opacity: 30%;')

    runtime.resetGroup('shadow', 'light')
    expect(runtime.getDirtyDefinitions('light')).toHaveLength(0)
    expect(runtime.getDirtyDefinitions('dark').map((item) => item.key)).toEqual(
      ['dark-shadow-card-opacity'],
    )
    expect(style?.textContent).not.toContain('--shadow-card-opacity: 12%;')
    expect(style?.textContent).toContain('--shadow-card-opacity: 30%;')
  })

  it('恢复 Stage 3B 外观不会清除 Stage 2 尺寸临时覆盖', () => {
    const storage = new MemoryStorage()
    const root = document.createElement('html')
    const cardPadding = findVisualTokenDefinition('card-padding-y')!
    const cardRadius = getAppearanceDefinition('radius-card')
    const dimensionRuntime = createVisualTokenTunerRuntime({
      enabled: true,
      root,
      storage,
      getComputedStyle: createComputedStyle(root),
    })
    const appearanceRuntime = createVisualAppearanceTunerRuntime({
      enabled: true,
      root,
      storage,
      getComputedStyle: createComputedStyle(root),
      getBaseline: (definition) => definition.defaultValue,
    })

    dimensionRuntime.setValue(cardPadding, 20)
    appearanceRuntime.setValue(cardRadius, 22)
    appearanceRuntime.resetAll()

    expect(root.style.getPropertyValue(cardPadding.cssVar)).toBe('20px')
    expect(root.style.getPropertyValue(cardRadius.cssVar)).toBe('')
    expect(storage.values.get(VISUAL_TOKEN_TUNER_STORAGE_KEY)).toContain(
      '"--layout-card-padding-y":"20px"',
    )
    expect(storage.values.has(VISUAL_APPEARANCE_TUNER_STORAGE_KEY)).toBe(false)
  })

  it('生产态不读取或写入 V3 存储，也不注入外观覆盖', () => {
    const storage = new MemoryStorage()
    const root = document.createElement('html')
    const runtime = createVisualAppearanceTunerRuntime({
      enabled: false,
      root,
      storage,
      getComputedStyle: createComputedStyle(root),
    })

    runtime.setValue(getAppearanceDefinition('radius-card'), 22)
    runtime.restore()
    runtime.resetAll()

    expect(runtime.enabled).toBe(false)
    expect(root.style.getPropertyValue('--radius-card')).toBe('')
    expect(storage.values).toHaveLength(0)
  })
})
