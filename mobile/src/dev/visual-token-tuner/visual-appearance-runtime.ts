import {
  formatVisualTokenValue,
  isVisualTokenTunerEnabled,
  type VisualTokenStorage,
} from './visual-token-runtime'
import {
  type VisualAppearanceTokenDefinition,
  type VisualAppearanceTokenGroupKey,
  type VisualColorTheme,
  visualAppearanceTokenRegistry,
} from './visual-token-registry'

export const VISUAL_APPEARANCE_TUNER_STORAGE_KEY =
  'control-center.mobile.visual-token-tuner-v3'

const VISUAL_APPEARANCE_OVERRIDE_STYLE_ID =
  'control-center-mobile-visual-token-tuner-appearance-overrides'
const visualThemes: readonly VisualColorTheme[] = ['light', 'dark']

export interface VisualAppearanceRuntimeOptions {
  enabled?: boolean
  registry?: readonly VisualAppearanceTokenDefinition[]
  getBaseline?: (definition: VisualAppearanceTokenDefinition) => number | null
  root?: HTMLElement | null
  storage?: VisualTokenStorage | null
  document?: Document | null
  getComputedStyle?: (element: Element) => CSSStyleDeclaration
}

export type VisualAppearanceValues = Record<string, number>

interface StoredVisualAppearanceOverridesV3 {
  version: 3
  common: Record<string, string>
  shadows: Record<VisualColorTheme, Record<string, string>>
}

interface ParsedVisualAppearanceOverrides {
  common: Map<string, number>
  shadows: Record<VisualColorTheme, Map<string, number>>
}

function getDefaultRoot(): HTMLElement | null {
  if (typeof document === 'undefined') return null
  return document.documentElement
}

function getDefaultDocument(): Document | null {
  if (typeof document === 'undefined') return null
  return document
}

function getDefaultComputedStyle(element: Element): CSSStyleDeclaration | null {
  if (typeof window === 'undefined') return null
  return window.getComputedStyle(element)
}

function getDefaultStorage(): VisualTokenStorage | null {
  if (typeof window === 'undefined') return null

  try {
    return window.localStorage
  } catch {
    return null
  }
}

function parseNumericValue(rawValue: string | number): number | null {
  const parsed =
    typeof rawValue === 'number' ? rawValue : Number.parseFloat(rawValue)
  return Number.isFinite(parsed) ? parsed : null
}

function normalizeValue(
  definition: VisualAppearanceTokenDefinition,
  value: number,
): number {
  const limited = Math.min(definition.max, Math.max(definition.min, value))
  const stepped =
    definition.min +
    Math.round((limited - definition.min) / definition.step) * definition.step

  return Number.parseFloat(stepped.toFixed(4))
}

function selectorMatchesTheme(
  selector: string,
  theme: VisualColorTheme,
): boolean {
  return (
    selector.includes(':root') &&
    new RegExp(`data-theme\\s*=\\s*['\"]?${theme}\\b`, 'u').test(selector)
  )
}

function selectorMatchesBaseline(
  selector: string,
  definition: VisualAppearanceTokenDefinition,
): boolean {
  if (!selector.includes(':root')) return false
  if (definition.theme) return selectorMatchesTheme(selector, definition.theme)
  return !selector.includes('data-theme')
}

function readBaselineFromRules(
  rules: CSSRuleList,
  definition: VisualAppearanceTokenDefinition,
): number | null {
  for (const rule of Array.from(rules)) {
    const styleRule = rule as CSSStyleRule
    if (
      typeof styleRule.selectorText === 'string' &&
      selectorMatchesBaseline(styleRule.selectorText, definition)
    ) {
      const value = parseNumericValue(
        styleRule.style.getPropertyValue(definition.cssVar),
      )
      if (value !== null) return value
    }

    const nestedRules = (rule as CSSGroupingRule).cssRules
    if (nestedRules) {
      const nestedValue = readBaselineFromRules(nestedRules, definition)
      if (nestedValue !== null) return nestedValue
    }
  }
  return null
}

function readBaselineFromDocument(
  documentRef: Document | null,
  definition: VisualAppearanceTokenDefinition,
): number | null {
  if (!documentRef) return null

  for (const styleSheet of Array.from(documentRef.styleSheets)) {
    try {
      const value = readBaselineFromRules(styleSheet.cssRules, definition)
      if (value !== null) return value
    } catch {
      // Cross-origin stylesheets are never a Mobile Token baseline source.
    }
  }
  return null
}

function createEmptyThemeValues(): Record<
  VisualColorTheme,
  Map<string, number>
> {
  return {
    light: new Map(),
    dark: new Map(),
  }
}

function parseValues(
  values: Record<string, unknown>,
  registry: readonly VisualAppearanceTokenDefinition[],
  theme?: VisualColorTheme,
): Map<string, number> {
  return new Map(
    registry.flatMap((definition) => {
      if ((definition.theme ?? undefined) !== theme) return []
      const parsed = parseNumericValue(
        values[definition.cssVar] as string | number,
      )
      return parsed === null
        ? []
        : [[definition.cssVar, normalizeValue(definition, parsed)] as const]
    }),
  )
}

function parseStoredOverrides(
  rawValue: string | null,
  registry: readonly VisualAppearanceTokenDefinition[],
): ParsedVisualAppearanceOverrides {
  const empty: ParsedVisualAppearanceOverrides = {
    common: new Map(),
    shadows: createEmptyThemeValues(),
  }
  if (!rawValue) return empty

  try {
    const payload: unknown = JSON.parse(rawValue)
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
      return empty
    }

    const value = payload as Record<string, unknown>
    if (value.version !== 3) return empty
    const common =
      value.common &&
      typeof value.common === 'object' &&
      !Array.isArray(value.common)
        ? (value.common as Record<string, unknown>)
        : {}
    const shadows =
      value.shadows &&
      typeof value.shadows === 'object' &&
      !Array.isArray(value.shadows)
        ? (value.shadows as Record<string, unknown>)
        : {}

    return {
      common: parseValues(common, registry),
      shadows: {
        light: parseValues(
          shadows.light &&
            typeof shadows.light === 'object' &&
            !Array.isArray(shadows.light)
            ? (shadows.light as Record<string, unknown>)
            : {},
          registry,
          'light',
        ),
        dark: parseValues(
          shadows.dark &&
            typeof shadows.dark === 'object' &&
            !Array.isArray(shadows.dark)
            ? (shadows.dark as Record<string, unknown>)
            : {},
          registry,
          'dark',
        ),
      },
    }
  } catch {
    return empty
  }
}

export interface VisualAppearanceTunerRuntime {
  readonly enabled: boolean
  readBaseline(definition: VisualAppearanceTokenDefinition): number
  readValue(definition: VisualAppearanceTokenDefinition): number
  readValues(): VisualAppearanceValues
  setValue(definition: VisualAppearanceTokenDefinition, value: number): void
  resetValue(definition: VisualAppearanceTokenDefinition): void
  resetGroup(
    group: VisualAppearanceTokenGroupKey,
    theme?: VisualColorTheme,
  ): void
  resetAll(): void
  restore(): void
  getDirtyDefinitions(
    theme?: VisualColorTheme,
  ): readonly VisualAppearanceTokenDefinition[]
  toCssVariables(): string
  toJson(): string
}

export function createVisualAppearanceTunerRuntime(
  options: VisualAppearanceRuntimeOptions = {},
): VisualAppearanceTunerRuntime {
  const enabled = options.enabled ?? isVisualTokenTunerEnabled()
  const registry = options.registry ?? visualAppearanceTokenRegistry
  const root = options.root ?? getDefaultRoot()
  const documentRef = options.document ?? getDefaultDocument()
  const storage = enabled
    ? options.storage === undefined
      ? getDefaultStorage()
      : options.storage
    : null
  const readComputedStyle = options.getComputedStyle ?? getDefaultComputedStyle
  const isAvailable = enabled && Boolean(root)
  const baselineValues = new Map<string, number>()
  const commonOverrides = new Map<string, number>()
  const shadowOverrides = createEmptyThemeValues()
  const canApplyThemeScopedOverrides =
    isAvailable && Boolean(documentRef) && root === documentRef?.documentElement

  function baselineKey(definition: VisualAppearanceTokenDefinition): string {
    return `${definition.theme ?? 'common'}:${definition.cssVar}`
  }

  function readBaseline(definition: VisualAppearanceTokenDefinition): number {
    const key = baselineKey(definition)
    const cached = baselineValues.get(key)
    if (cached !== undefined) return cached

    const configured = options.getBaseline?.(definition)
    const fromDocument = readBaselineFromDocument(documentRef, definition)
    let fromComputed: number | null = null
    if (
      root &&
      readComputedStyle &&
      (!definition.theme || root.dataset.theme === definition.theme)
    ) {
      fromComputed = parseNumericValue(
        readComputedStyle(root)?.getPropertyValue(definition.cssVar).trim() ??
          '',
      )
    }
    const baseline =
      configured ?? fromDocument ?? fromComputed ?? definition.defaultValue
    const normalized = normalizeValue(definition, baseline)
    baselineValues.set(key, normalized)
    return normalized
  }

  function overrideMap(
    definition: VisualAppearanceTokenDefinition,
  ): Map<string, number> {
    return definition.theme
      ? shadowOverrides[definition.theme]
      : commonOverrides
  }

  function readValue(definition: VisualAppearanceTokenDefinition): number {
    return (
      overrideMap(definition).get(definition.cssVar) ?? readBaseline(definition)
    )
  }

  function readValues(): VisualAppearanceValues {
    return Object.fromEntries(
      registry.map((definition) => [definition.key, readValue(definition)]),
    )
  }

  function hasOverrides(): boolean {
    return (
      commonOverrides.size > 0 ||
      visualThemes.some((theme) => shadowOverrides[theme].size > 0)
    )
  }

  function removeRuntimeOverrides(): void {
    if (canApplyThemeScopedOverrides && documentRef) {
      documentRef.getElementById(VISUAL_APPEARANCE_OVERRIDE_STYLE_ID)?.remove()
      return
    }
    if (!root) return
    for (const cssVar of new Set(
      registry.map((definition) => definition.cssVar),
    )) {
      root.style.removeProperty(cssVar)
    }
  }

  function applyRuntimeOverrides(): void {
    if (canApplyThemeScopedOverrides && documentRef) {
      const commonDeclarations = registry.flatMap((definition) => {
        if (definition.theme) return []
        const value = commonOverrides.get(definition.cssVar)
        return value === undefined
          ? []
          : [
              `  ${definition.cssVar}: ${formatVisualTokenValue(value, definition.unit)};`,
            ]
      })
      const themedRules = visualThemes
        .map((theme) => {
          const declarations = registry.flatMap((definition) => {
            if (definition.theme !== theme) return []
            const value = shadowOverrides[theme].get(definition.cssVar)
            return value === undefined
              ? []
              : [
                  `  ${definition.cssVar}: ${formatVisualTokenValue(value, definition.unit)};`,
                ]
          })
          return declarations.length > 0
            ? [`:root[data-theme='${theme}'] {`, ...declarations, '}'].join(
                '\n',
              )
            : ''
        })
        .filter(Boolean)
      const rules = [
        commonDeclarations.length > 0
          ? [':root {', ...commonDeclarations, '}'].join('\n')
          : '',
        ...themedRules,
      ]
        .filter(Boolean)
        .join('\n\n')
      const existing = documentRef.getElementById(
        VISUAL_APPEARANCE_OVERRIDE_STYLE_ID,
      ) as HTMLStyleElement | null

      if (!rules) {
        existing?.remove()
        return
      }

      const style = existing ?? documentRef.createElement('style')
      style.id = VISUAL_APPEARANCE_OVERRIDE_STYLE_ID
      style.textContent = rules
      if (!existing) documentRef.head.append(style)
      return
    }

    if (!root) return
    removeRuntimeOverrides()
    for (const definition of registry) {
      if (definition.theme && root.dataset.theme !== definition.theme) continue
      const value = overrideMap(definition).get(definition.cssVar)
      if (value === undefined) continue
      root.style.setProperty(
        definition.cssVar,
        formatVisualTokenValue(value, definition.unit),
      )
    }
  }

  function persist(): void {
    if (!isAvailable || !storage) return

    try {
      if (!hasOverrides()) {
        storage.removeItem(VISUAL_APPEARANCE_TUNER_STORAGE_KEY)
        return
      }
      const payload: StoredVisualAppearanceOverridesV3 = {
        version: 3,
        common: Object.fromEntries(
          [...commonOverrides].map(([cssVar, value]) => {
            const definition = registry.find(
              (item) => !item.theme && item.cssVar === cssVar,
            )!
            return [cssVar, formatVisualTokenValue(value, definition.unit)]
          }),
        ),
        shadows: Object.fromEntries(
          visualThemes.map((theme) => [
            theme,
            Object.fromEntries(
              [...shadowOverrides[theme]].map(([cssVar, value]) => {
                const definition = registry.find(
                  (item) => item.theme === theme && item.cssVar === cssVar,
                )!
                return [cssVar, formatVisualTokenValue(value, definition.unit)]
              }),
            ),
          ]),
        ) as StoredVisualAppearanceOverridesV3['shadows'],
      }
      storage.setItem(
        VISUAL_APPEARANCE_TUNER_STORAGE_KEY,
        JSON.stringify(payload),
      )
    } catch {
      // 开发工具临时保存失败不应阻塞真实页面预览。
    }
  }

  function setValue(
    definition: VisualAppearanceTokenDefinition,
    value: number,
  ): void {
    if (!isAvailable || !Number.isFinite(value)) return
    const normalized = normalizeValue(definition, value)
    const target = overrideMap(definition)
    if (normalized === readBaseline(definition)) {
      target.delete(definition.cssVar)
    } else {
      target.set(definition.cssVar, normalized)
    }
    applyRuntimeOverrides()
    persist()
  }

  function resetValue(definition: VisualAppearanceTokenDefinition): void {
    if (!isAvailable) return
    overrideMap(definition).delete(definition.cssVar)
    applyRuntimeOverrides()
    persist()
  }

  function resetGroup(
    group: VisualAppearanceTokenGroupKey,
    theme?: VisualColorTheme,
  ): void {
    if (!isAvailable) return
    for (const definition of registry) {
      if (definition.group !== group) continue
      if (theme && definition.theme !== theme) continue
      if (!theme && definition.theme && group === 'shadow') {
        shadowOverrides[definition.theme].delete(definition.cssVar)
        continue
      }
      overrideMap(definition).delete(definition.cssVar)
    }
    applyRuntimeOverrides()
    persist()
  }

  function resetAll(): void {
    if (!isAvailable) return
    commonOverrides.clear()
    for (const theme of visualThemes) shadowOverrides[theme].clear()
    removeRuntimeOverrides()
    persist()
  }

  function restore(): void {
    if (!isAvailable) return
    commonOverrides.clear()
    for (const theme of visualThemes) shadowOverrides[theme].clear()
    removeRuntimeOverrides()
    if (!storage) return

    let rawValue: string | null
    try {
      rawValue = storage.getItem(VISUAL_APPEARANCE_TUNER_STORAGE_KEY)
    } catch {
      return
    }

    const stored = parseStoredOverrides(rawValue, registry)
    for (const definition of registry) {
      const values = definition.theme
        ? stored.shadows[definition.theme]
        : stored.common
      const value = values.get(definition.cssVar)
      if (value === undefined || value === readBaseline(definition)) continue
      overrideMap(definition).set(definition.cssVar, value)
    }
    applyRuntimeOverrides()

    if (rawValue && !hasOverrides()) {
      try {
        storage.removeItem(VISUAL_APPEARANCE_TUNER_STORAGE_KEY)
      } catch {
        // 开发工具的清理失败不应阻塞真实页面预览。
      }
    }
  }

  function getDirtyDefinitions(
    theme?: VisualColorTheme,
  ): readonly VisualAppearanceTokenDefinition[] {
    return registry.filter(
      (definition) =>
        (!theme || definition.theme === theme) &&
        overrideMap(definition).has(definition.cssVar),
    )
  }

  function toCssVariables(): string {
    const commonLines = registry
      .filter((definition) => !definition.theme)
      .map(
        (definition) =>
          `  ${definition.cssVar}: ${formatVisualTokenValue(
            readValue(definition),
            definition.unit,
          )};`,
      )
    const themedRules = visualThemes.map((theme) => {
      const lines = registry
        .filter((definition) => definition.theme === theme)
        .map(
          (definition) =>
            `  ${definition.cssVar}: ${formatVisualTokenValue(
              readValue(definition),
              definition.unit,
            )};`,
        )
      return [`:root[data-theme='${theme}'] {`, ...lines, '}'].join('\n')
    })
    return [':root {', ...commonLines, '}', ...themedRules].join('\n\n')
  }

  function toJson(): string {
    return JSON.stringify(
      {
        common: Object.fromEntries(
          registry
            .filter((definition) => !definition.theme)
            .map((definition) => [
              definition.cssVar,
              formatVisualTokenValue(readValue(definition), definition.unit),
            ]),
        ),
        shadows: Object.fromEntries(
          visualThemes.map((theme) => [
            theme,
            Object.fromEntries(
              registry
                .filter((definition) => definition.theme === theme)
                .map((definition) => [
                  definition.cssVar,
                  formatVisualTokenValue(
                    readValue(definition),
                    definition.unit,
                  ),
                ]),
            ),
          ]),
        ),
      },
      null,
      2,
    )
  }

  return {
    enabled: isAvailable,
    readBaseline,
    readValue,
    readValues,
    setValue,
    resetValue,
    resetGroup,
    resetAll,
    restore,
    getDirtyDefinitions,
    toCssVariables,
    toJson,
  }
}

let hasInstalledVisualAppearanceTunerSync = false

export function initializeVisualAppearanceTuner(): void {
  const runtime = createVisualAppearanceTunerRuntime()
  runtime.restore()

  if (
    !runtime.enabled ||
    hasInstalledVisualAppearanceTunerSync ||
    typeof window === 'undefined'
  ) {
    return
  }

  window.addEventListener('storage', (event) => {
    if (event.key === VISUAL_APPEARANCE_TUNER_STORAGE_KEY) runtime.restore()
  })
  hasInstalledVisualAppearanceTunerSync = true
}
