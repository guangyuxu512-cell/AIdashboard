import { describe, expect, it } from 'vitest'

import {
  VISUAL_TOKEN_TUNER_STORAGE_KEY,
  createVisualTokenTunerRuntime,
  findVisualColorTokenDefinition,
  findVisualTokenDefinition,
  getVisualColorContrastRatio,
  isVisualTokenTunerEnabled,
  visualTokenRegistry,
  type VisualTokenStorage,
} from '@/dev/visual-token-tuner'

class MemoryStorage implements VisualTokenStorage {
  readonly values = new Map<string, string>()
  getCalls = 0
  setCalls = 0
  removeCalls = 0

  getItem(key: string): string | null {
    this.getCalls += 1
    return this.values.get(key) ?? null
  }

  setItem(key: string, value: string): void {
    this.setCalls += 1
    this.values.set(key, value)
  }

  removeItem(key: string): void {
    this.removeCalls += 1
    this.values.delete(key)
  }
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
          visualTokenRegistry
            .find((definition) => definition.cssVar === cssVar)
            ?.defaultValue.toString() ?? ''
        )
      },
    } as CSSStyleDeclaration
  }
}

function getDefinition(key: string) {
  const definition = findVisualTokenDefinition(key)
  if (!definition) throw new Error(`缺少测试 Token：${key}`)
  return definition
}

function getColorDefinition(key: string) {
  const definition = findVisualColorTokenDefinition(key)
  if (!definition) throw new Error(`缺少测试颜色 Token：${key}`)
  return definition
}

function readTestColorBaseline(
  definition: ReturnType<typeof getColorDefinition>,
): string {
  return definition.theme === 'light' ? '#f4f6f8' : '#101820'
}

describe('Visual Token Tuner runtime', () => {
  it('只公开语义间距 Token，不把原子刻度当作局部调参控件', () => {
    expect(
      visualTokenRegistry.some((definition) =>
        definition.cssVar.startsWith('--space-'),
      ),
    ).toBe(false)
    expect(getDefinition('card-leading-content-gap').cssVar).toBe(
      '--layout-card-leading-content-gap',
    )
    expect(getDefinition('summary-metric-gap').cssVar).toBe(
      '--layout-summary-metric-gap',
    )
    expect(getDefinition('runtime-leading-content-gap').cssVar).toBe(
      '--layout-runtime-summary-leading-content-gap',
    )
    expect(getDefinition('capability-row-gap').cssVar).toBe(
      '--layout-capability-row-gap',
    )
  })

  it('在开发态从实际计算值读取并实时覆盖已登记 Token', () => {
    const root = document.createElement('html')
    const storage = new MemoryStorage()
    const definition = getDefinition('card-padding-y')
    const runtime = createVisualTokenTunerRuntime({
      enabled: true,
      root,
      storage,
      getComputedStyle: createComputedStyle(root),
    })

    root.style.setProperty(definition.cssVar, '17px')
    expect(runtime.readValue(definition)).toBe(17)

    runtime.setValue(definition, 19)
    expect(root.style.getPropertyValue(definition.cssVar)).toBe('19px')
    expect(runtime.readValue(definition)).toBe(19)
    expect(runtime.getDirtyDefinitions().map((item) => item.key)).toContain(
      'card-padding-y',
    )
    expect(storage.values.get(VISUAL_TOKEN_TUNER_STORAGE_KEY)).toContain(
      '"--layout-card-padding-y":"19px"',
    )
  })

  it('支持单项恢复、全部恢复与可导出的最终值', () => {
    const root = document.createElement('html')
    const storage = new MemoryStorage()
    const cardPadding = getDefinition('card-padding-y')
    const summaryHeight = getDefinition('summary-height')
    const runtime = createVisualTokenTunerRuntime({
      enabled: true,
      root,
      storage,
      getComputedStyle: createComputedStyle(root),
    })

    runtime.setValue(cardPadding, 20)
    runtime.setValue(summaryHeight, 100)
    expect(runtime.toCssVariables()).toContain('--layout-card-padding-y: 20px;')
    expect(runtime.toJson()).toContain('"--layout-summary-height": "100px"')

    runtime.resetValue(cardPadding)
    expect(root.style.getPropertyValue(cardPadding.cssVar)).toBe('')
    expect(runtime.readValue(cardPadding)).toBe(cardPadding.defaultValue)
    expect(runtime.getDirtyDefinitions().map((item) => item.key)).toEqual([
      'summary-height',
    ])

    runtime.resetAll()
    expect(root.style.getPropertyValue(summaryHeight.cssVar)).toBe('')
    expect(runtime.getDirtyDefinitions()).toHaveLength(0)
    expect(storage.values.has(VISUAL_TOKEN_TUNER_STORAGE_KEY)).toBe(false)
  })

  it('刷新后会在开发启动阶段恢复上次的临时覆盖', () => {
    const storage = new MemoryStorage()
    const definition = getDefinition('card-leading-slot')
    const firstRoot = document.createElement('html')
    const firstRuntime = createVisualTokenTunerRuntime({
      enabled: true,
      root: firstRoot,
      storage,
      getComputedStyle: createComputedStyle(firstRoot),
    })

    firstRuntime.setValue(definition, 60)

    const refreshedRoot = document.createElement('html')
    const refreshedRuntime = createVisualTokenTunerRuntime({
      enabled: true,
      root: refreshedRoot,
      storage,
      getComputedStyle: createComputedStyle(refreshedRoot),
    })
    refreshedRuntime.restore()

    expect(refreshedRoot.style.getPropertyValue(definition.cssVar)).toBe('60px')
    expect(refreshedRuntime.readValue(definition)).toBe(60)
  })

  it('同步恢复会先移除过期覆盖，再应用其他窗口写入的临时值', () => {
    const storage = new MemoryStorage()
    const definition = getDefinition('summary-height')
    const root = document.createElement('html')
    const runtime = createVisualTokenTunerRuntime({
      enabled: true,
      root,
      storage,
      getComputedStyle: createComputedStyle(root),
    })

    root.style.setProperty(definition.cssVar, '104px')
    runtime.restore()
    expect(root.style.getPropertyValue(definition.cssVar)).toBe('')

    storage.setItem(
      VISUAL_TOKEN_TUNER_STORAGE_KEY,
      JSON.stringify({ [definition.cssVar]: '100px' }),
    )
    runtime.restore()
    expect(root.style.getPropertyValue(definition.cssVar)).toBe('100px')
  })

  it('固化后的默认值会清理等于新基线的遗留临时记录', () => {
    const storage = new MemoryStorage()
    const definition = getDefinition('summary-height')
    const root = document.createElement('html')
    const runtime = createVisualTokenTunerRuntime({
      enabled: true,
      root,
      storage,
      getComputedStyle: createComputedStyle(root),
    })

    storage.setItem(
      VISUAL_TOKEN_TUNER_STORAGE_KEY,
      JSON.stringify({
        [definition.cssVar]: `${definition.defaultValue}${definition.unit}`,
      }),
    )
    runtime.restore()

    expect(root.style.getPropertyValue(definition.cssVar)).toBe('')
    expect(storage.values.has(VISUAL_TOKEN_TUNER_STORAGE_KEY)).toBe(false)
  })

  it('会清理历史原子间距覆盖，且不会重新注入页面', () => {
    const storage = new MemoryStorage()
    const definition = getDefinition('card-leading-content-gap')
    const root = document.createElement('html')
    const runtime = createVisualTokenTunerRuntime({
      enabled: true,
      root,
      storage,
      getComputedStyle: createComputedStyle(root),
    })

    root.style.setProperty('--space-1', '2px')
    root.style.setProperty('--space-2', '16px')
    storage.setItem(
      VISUAL_TOKEN_TUNER_STORAGE_KEY,
      JSON.stringify({
        '--space-1': '2px',
        '--space-2': '16px',
        [definition.cssVar]: '12px',
      }),
    )

    runtime.restore()

    expect(root.style.getPropertyValue('--space-1')).toBe('')
    expect(root.style.getPropertyValue('--space-2')).toBe('')
    expect(root.style.getPropertyValue(definition.cssVar)).toBe('12px')
    expect(storage.values.get(VISUAL_TOKEN_TUNER_STORAGE_KEY)).toBe(
      JSON.stringify({
        version: 2,
        dimensions: { [definition.cssVar]: '12px' },
        colors: { light: {}, dark: {} },
      }),
    )
  })

  it('按主题隔离保存颜色，恢复颜色不会清除 Stage 2 尺寸覆盖', () => {
    const root = document.createElement('html')
    const storage = new MemoryStorage()
    const dimension = getDefinition('card-padding-y')
    const lightSurface = getColorDefinition('light-bg-app')
    const darkSurface = getColorDefinition('dark-bg-app')
    const runtime = createVisualTokenTunerRuntime({
      enabled: true,
      root,
      storage,
      getComputedStyle: createComputedStyle(root),
      getColorBaseline: readTestColorBaseline,
    })

    runtime.setValue(dimension, 20)
    expect(runtime.setColorValue(lightSurface, '#e8edf2')).toBe(true)
    expect(runtime.setColorValue(darkSurface, '#0f151d')).toBe(true)

    expect(runtime.readColorValue(lightSurface)).toBe('#e8edf2')
    expect(runtime.readColorValue(darkSurface)).toBe('#0f151d')
    expect(runtime.getDirtyColorDefinitions('light')).toHaveLength(1)
    expect(runtime.getDirtyColorDefinitions('dark')).toHaveLength(1)
    expect(runtime.toColorCssVariables()).toContain(
      ":root[data-theme='light'] {",
    )
    expect(runtime.toColorCssVariables()).toContain(
      ":root[data-theme='dark'] {",
    )
    expect(runtime.toColorJson()).toContain('"light"')
    expect(runtime.toColorJson()).toContain('"dark"')

    runtime.resetColorTheme('light')
    expect(runtime.readColorValue(lightSurface)).toBe(
      runtime.readColorBaseline(lightSurface),
    )
    expect(runtime.readColorValue(darkSurface)).toBe('#0f151d')
    expect(runtime.readValue(dimension)).toBe(20)

    runtime.resetAllColors()
    expect(runtime.getDirtyColorDefinitions()).toHaveLength(0)
    expect(runtime.readValue(dimension)).toBe(20)
    expect(storage.values.get(VISUAL_TOKEN_TUNER_STORAGE_KEY)).toContain(
      '"dimensions":{"--layout-card-padding-y":"20px"}',
    )
  })

  it('拒绝无效 HEX，并对可读性对比度提供稳定计算', () => {
    const root = document.createElement('html')
    const runtime = createVisualTokenTunerRuntime({
      enabled: true,
      root,
      storage: new MemoryStorage(),
      getComputedStyle: createComputedStyle(root),
      getColorBaseline: readTestColorBaseline,
    })
    const surface = getColorDefinition('light-bg-app')

    expect(runtime.setColorValue(surface, 'rgb(0, 0, 0)')).toBe(false)
    expect(runtime.readColorValue(surface)).toBe(
      runtime.readColorBaseline(surface),
    )
    expect(getVisualColorContrastRatio('#000000', '#ffffff')).toBe(21)
    expect(getVisualColorContrastRatio('#000', '#ffffff')).toBeNull()
  })

  it('生产态不读取存储、不注入覆盖，也不启用工具', () => {
    const root = document.createElement('html')
    const storage = new MemoryStorage()
    const definition = getDefinition('touch-target-min')
    const runtime = createVisualTokenTunerRuntime({
      enabled: false,
      root,
      storage,
      getComputedStyle: createComputedStyle(root),
    })

    runtime.restore()
    runtime.setValue(definition, 36)
    runtime.resetAll()

    expect(runtime.enabled).toBe(false)
    expect(root.style.getPropertyValue(definition.cssVar)).toBe('')
    expect(storage.getCalls).toBe(0)
    expect(storage.setCalls).toBe(0)
    expect(storage.removeCalls).toBe(0)
    expect(isVisualTokenTunerEnabled({ DEV: false })).toBe(false)
    expect(isVisualTokenTunerEnabled({ DEV: true })).toBe(true)
    expect(
      isVisualTokenTunerEnabled({ DEV: true, VITE_VISUAL_TUNER: 'false' }),
    ).toBe(false)
  })
})
