import {
  type VisualColorTheme,
  type VisualColorTokenDefinition,
  type VisualTokenDefinition,
  type VisualTokenUnit,
  visualColorTokenRegistry,
  visualTokenRegistry,
} from './visual-token-registry'

export const VISUAL_TOKEN_TUNER_STORAGE_KEY =
  'control-center.mobile.visual-token-tuner-v1'

const legacyVisualTokenCssVars = ['--space-1', '--space-2'] as const
const VISUAL_COLOR_OVERRIDE_STYLE_ID =
  'control-center-mobile-visual-token-tuner-color-overrides'
const visualColorThemes: readonly VisualColorTheme[] = ['light', 'dark']
const hexColorPattern = /^#[0-9a-fA-F]{6}$/

export interface VisualTokenTunerEnvironment {
  DEV?: boolean
  VITE_VISUAL_TUNER?: string
}

export interface VisualTokenStorage {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

export interface VisualTokenRuntimeOptions {
  enabled?: boolean
  registry?: readonly VisualTokenDefinition[]
  colorRegistry?: readonly VisualColorTokenDefinition[]
  getColorBaseline?: (definition: VisualColorTokenDefinition) => string | null
  root?: HTMLElement | null
  storage?: VisualTokenStorage | null
  document?: Document | null
  getComputedStyle?: (element: Element) => CSSStyleDeclaration
}

export type VisualTokenValues = Record<string, number>
export type VisualTokenColorValues = Record<
  VisualColorTheme,
  Record<string, string>
>

interface StoredVisualTokenOverridesV2 {
  version: 2
  dimensions: Record<string, string>
  colors: Record<VisualColorTheme, Record<string, string>>
}

interface ParsedVisualTokenOverrides {
  dimensions: Map<string, number>
  colors: Record<VisualColorTheme, Map<string, string>>
}

export function isVisualTokenTunerEnabled(
  environment: VisualTokenTunerEnvironment = import.meta.env,
): boolean {
  return Boolean(environment.DEV) && environment.VITE_VISUAL_TUNER !== 'false'
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

export function normalizeVisualColorValue(value: string): string | null {
  const normalized = value.trim()
  return hexColorPattern.test(normalized) ? normalized.toLowerCase() : null
}

function normalizeValue(
  definition: VisualTokenDefinition,
  value: number,
): number {
  const limited = Math.min(definition.max, Math.max(definition.min, value))
  const stepped =
    definition.min +
    Math.round((limited - definition.min) / definition.step) * definition.step

  return Number.parseFloat(stepped.toFixed(4))
}

export function formatVisualTokenValue(
  value: number,
  unit: VisualTokenUnit,
): string {
  return `${value}${unit}`
}

export function getVisualColorContrastRatio(
  foreground: string,
  background: string,
): number | null {
  const normalizedForeground = normalizeVisualColorValue(foreground)
  const normalizedBackground = normalizeVisualColorValue(background)
  if (!normalizedForeground || !normalizedBackground) return null

  const relativeLuminance = (color: string): number => {
    const channels = [1, 3, 5].map(
      (offset) => Number.parseInt(color.slice(offset, offset + 2), 16) / 255,
    )
    const [red, green, blue] = channels.map((channel) =>
      channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4,
    )
    return red * 0.2126 + green * 0.7152 + blue * 0.0722
  }

  const [lightest, darkest] = [
    relativeLuminance(normalizedForeground),
    relativeLuminance(normalizedBackground),
  ].sort((left, right) => right - left)
  return (lightest + 0.05) / (darkest + 0.05)
}

function isDefaultValue(
  definition: VisualTokenDefinition,
  value: number,
): boolean {
  return Math.abs(value - definition.defaultValue) < 0.0001
}

function selectorMatchesColorTheme(
  selector: string,
  theme: VisualColorTheme,
): boolean {
  return (
    selector.includes(':root') &&
    new RegExp(`data-theme\\s*=\\s*['\"]?${theme}\\b`, 'u').test(selector)
  )
}

function readColorBaselineFromRules(
  rules: CSSRuleList,
  definition: VisualColorTokenDefinition,
): string | null {
  for (const rule of Array.from(rules)) {
    const styleRule = rule as CSSStyleRule
    if (
      typeof styleRule.selectorText === 'string' &&
      selectorMatchesColorTheme(styleRule.selectorText, definition.theme)
    ) {
      const value = normalizeVisualColorValue(
        styleRule.style.getPropertyValue(definition.cssVar),
      )
      if (value) return value
    }

    const nestedRules = (rule as CSSGroupingRule).cssRules
    if (nestedRules) {
      const nestedValue = readColorBaselineFromRules(nestedRules, definition)
      if (nestedValue) return nestedValue
    }
  }
  return null
}

function readColorBaselineFromDocument(
  documentRef: Document | null,
  definition: VisualColorTokenDefinition,
): string | null {
  if (!documentRef) return null

  for (const styleSheet of Array.from(documentRef.styleSheets)) {
    try {
      const value = readColorBaselineFromRules(styleSheet.cssRules, definition)
      if (value) return value
    } catch {
      // Third-party stylesheet may be cross-origin; it is never a Mobile Token source.
    }
  }
  return null
}

function createEmptyColorOverrides(): Record<
  VisualColorTheme,
  Map<string, string>
> {
  return {
    light: new Map(),
    dark: new Map(),
  }
}

function parseDimensionOverrides(
  values: Record<string, unknown>,
  registry: readonly VisualTokenDefinition[],
): Map<string, number> {
  return new Map(
    registry.flatMap((definition) => {
      const parsed = parseNumericValue(
        values[definition.cssVar] as string | number,
      )
      return parsed === null
        ? []
        : [[definition.cssVar, normalizeValue(definition, parsed)] as const]
    }),
  )
}

function parseColorOverrides(
  values: Record<string, unknown>,
  theme: VisualColorTheme,
  registry: readonly VisualColorTokenDefinition[],
): Map<string, string> {
  return new Map(
    registry.flatMap((definition) => {
      if (definition.theme !== theme) return []
      const rawValue = values[definition.cssVar]
      const normalized =
        typeof rawValue === 'string'
          ? normalizeVisualColorValue(rawValue)
          : null
      return normalized === null
        ? []
        : [[definition.cssVar, normalized] as const]
    }),
  )
}

function parseStoredOverrides(
  rawValue: string | null,
  registry: readonly VisualTokenDefinition[],
  colorRegistry: readonly VisualColorTokenDefinition[],
): ParsedVisualTokenOverrides {
  const empty: ParsedVisualTokenOverrides = {
    dimensions: new Map(),
    colors: createEmptyColorOverrides(),
  }
  if (!rawValue) return empty

  try {
    const payload: unknown = JSON.parse(rawValue)
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
      return empty
    }

    const values = payload as Record<string, unknown>
    if (values.version !== 2) {
      return {
        dimensions: parseDimensionOverrides(values, registry),
        colors: createEmptyColorOverrides(),
      }
    }

    const dimensions =
      values.dimensions &&
      typeof values.dimensions === 'object' &&
      !Array.isArray(values.dimensions)
        ? (values.dimensions as Record<string, unknown>)
        : {}
    const colors =
      values.colors &&
      typeof values.colors === 'object' &&
      !Array.isArray(values.colors)
        ? (values.colors as Record<string, unknown>)
        : {}

    return {
      dimensions: parseDimensionOverrides(dimensions, registry),
      colors: {
        light: parseColorOverrides(
          colors.light &&
            typeof colors.light === 'object' &&
            !Array.isArray(colors.light)
            ? (colors.light as Record<string, unknown>)
            : {},
          'light',
          colorRegistry,
        ),
        dark: parseColorOverrides(
          colors.dark &&
            typeof colors.dark === 'object' &&
            !Array.isArray(colors.dark)
            ? (colors.dark as Record<string, unknown>)
            : {},
          'dark',
          colorRegistry,
        ),
      },
    }
  } catch {
    return empty
  }
}

export interface VisualTokenTunerRuntime {
  readonly enabled: boolean
  readValue(definition: VisualTokenDefinition): number
  readValues(): VisualTokenValues
  setValue(definition: VisualTokenDefinition, value: number): void
  resetValue(definition: VisualTokenDefinition): void
  resetAll(): void
  resetAllOverrides(): void
  readColorBaseline(definition: VisualColorTokenDefinition): string
  readColorValue(definition: VisualColorTokenDefinition): string
  readColorValues(): VisualTokenColorValues
  setColorValue(definition: VisualColorTokenDefinition, value: string): boolean
  resetColorValue(definition: VisualColorTokenDefinition): void
  resetColorTheme(theme: VisualColorTheme): void
  resetAllColors(): void
  restore(): void
  getDirtyDefinitions(): readonly VisualTokenDefinition[]
  getDirtyColorDefinitions(
    theme?: VisualColorTheme,
  ): readonly VisualColorTokenDefinition[]
  toCssVariables(): string
  toJson(): string
  toColorCssVariables(): string
  toColorJson(): string
}

export function createVisualTokenTunerRuntime(
  options: VisualTokenRuntimeOptions = {},
): VisualTokenTunerRuntime {
  const enabled = options.enabled ?? isVisualTokenTunerEnabled()
  const registry = options.registry ?? visualTokenRegistry
  const colorRegistry = options.colorRegistry ?? visualColorTokenRegistry
  const root = options.root ?? getDefaultRoot()
  const documentRef = options.document ?? getDefaultDocument()
  const storage = enabled
    ? options.storage === undefined
      ? getDefaultStorage()
      : options.storage
    : null
  const readComputedStyle = options.getComputedStyle ?? getDefaultComputedStyle
  const isAvailable = enabled && Boolean(root)
  const colorOverrides = createEmptyColorOverrides()
  const colorBaselines = new Map<string, string>()
  const canApplyThemeScopedColorOverrides =
    isAvailable && Boolean(documentRef) && root === documentRef?.documentElement

  function readValue(definition: VisualTokenDefinition): number {
    if (!isAvailable || !root || !readComputedStyle) {
      return definition.defaultValue
    }

    const computed = readComputedStyle(root)
    const rawValue = computed?.getPropertyValue(definition.cssVar).trim() ?? ''
    const parsed = parseNumericValue(rawValue)
    return parsed === null ? definition.defaultValue : parsed
  }

  function readValues(): VisualTokenValues {
    return Object.fromEntries(
      registry.map((definition) => [definition.key, readValue(definition)]),
    )
  }

  function readColorBaseline(definition: VisualColorTokenDefinition): string {
    const key = `${definition.theme}:${definition.cssVar}`
    const cached = colorBaselines.get(key)
    if (cached) return cached

    const configured = options.getColorBaseline?.(definition)
    const fromConfigured = configured
      ? normalizeVisualColorValue(configured)
      : null
    const fromDocument = readColorBaselineFromDocument(documentRef, definition)
    let fromComputed: string | null = null
    if (root && root.dataset.theme === definition.theme && readComputedStyle) {
      const computed = readComputedStyle(root)
      if (computed) {
        fromComputed = normalizeVisualColorValue(
          computed.getPropertyValue(definition.cssVar),
        )
      }
    }
    const baseline = fromConfigured ?? fromDocument ?? fromComputed ?? ''
    if (baseline) colorBaselines.set(key, baseline)
    return baseline
  }

  function readColorValue(definition: VisualColorTokenDefinition): string {
    return (
      colorOverrides[definition.theme].get(definition.cssVar) ??
      readColorBaseline(definition)
    )
  }

  function readColorValues(): VisualTokenColorValues {
    return Object.fromEntries(
      visualColorThemes.map((theme) => [
        theme,
        Object.fromEntries(
          colorRegistry
            .filter((definition) => definition.theme === theme)
            .map((definition) => [
              definition.cssVar,
              readColorValue(definition),
            ]),
        ),
      ]),
    ) as VisualTokenColorValues
  }

  function hasDimensionOverrides(): boolean {
    return registry.some(
      (definition) => !isDefaultValue(definition, readValue(definition)),
    )
  }

  function hasColorOverrides(): boolean {
    return visualColorThemes.some((theme) => colorOverrides[theme].size > 0)
  }

  function persist(): void {
    if (!isAvailable || !storage) return

    const dimensions = Object.fromEntries(
      registry.flatMap((definition) => {
        const value = readValue(definition)
        return isDefaultValue(definition, value)
          ? []
          : [
              [
                definition.cssVar,
                formatVisualTokenValue(value, definition.unit),
              ],
            ]
      }),
    )
    const colors = Object.fromEntries(
      visualColorThemes.map((theme) => [
        theme,
        Object.fromEntries(colorOverrides[theme]),
      ]),
    ) as StoredVisualTokenOverridesV2['colors']

    try {
      if (!hasDimensionOverrides() && !hasColorOverrides()) {
        storage.removeItem(VISUAL_TOKEN_TUNER_STORAGE_KEY)
        return
      }
      const payload: StoredVisualTokenOverridesV2 = {
        version: 2,
        dimensions,
        colors,
      }
      storage.setItem(VISUAL_TOKEN_TUNER_STORAGE_KEY, JSON.stringify(payload))
    } catch {
      // 开发工具的临时保存失败不应影响真实页面预览。
    }
  }

  function clearRuntimeDimensionOverrides(): void {
    if (!root) return

    for (const definition of registry) {
      root.style.removeProperty(definition.cssVar)
    }

    for (const cssVar of legacyVisualTokenCssVars) {
      root.style.removeProperty(cssVar)
    }
  }

  function applyColorRuntimeOverrides(): void {
    if (!canApplyThemeScopedColorOverrides || !documentRef) return

    const rules = visualColorThemes
      .map((theme) => {
        const declarations = colorRegistry.flatMap((definition) => {
          if (definition.theme !== theme) return []
          const value = colorOverrides[theme].get(definition.cssVar)
          return value ? [`  ${definition.cssVar}: ${value};`] : []
        })
        return declarations.length > 0
          ? [`:root[data-theme='${theme}'] {`, ...declarations, '}'].join('\n')
          : ''
      })
      .filter(Boolean)
      .join('\n\n')
    const existing = documentRef.getElementById(
      VISUAL_COLOR_OVERRIDE_STYLE_ID,
    ) as HTMLStyleElement | null

    if (!rules) {
      existing?.remove()
      return
    }

    const style = existing ?? documentRef.createElement('style')
    style.id = VISUAL_COLOR_OVERRIDE_STYLE_ID
    style.textContent = rules
    if (!existing) documentRef.head.append(style)
  }

  function setValue(definition: VisualTokenDefinition, value: number): void {
    if (!isAvailable || !root || !Number.isFinite(value)) return

    const normalized = normalizeValue(definition, value)
    if (isDefaultValue(definition, normalized)) {
      root.style.removeProperty(definition.cssVar)
    } else {
      root.style.setProperty(
        definition.cssVar,
        formatVisualTokenValue(normalized, definition.unit),
      )
    }
    persist()
  }

  function resetValue(definition: VisualTokenDefinition): void {
    if (!isAvailable || !root) return
    root.style.removeProperty(definition.cssVar)
    persist()
  }

  function resetAll(): void {
    if (!isAvailable || !root) return
    clearRuntimeDimensionOverrides()
    persist()
  }

  /** 一次性清理 V2 尺寸与颜色，避免跨窗口同步出现中间状态。 */
  function resetAllOverrides(): void {
    if (!isAvailable || !root) return
    clearRuntimeDimensionOverrides()
    for (const theme of visualColorThemes) colorOverrides[theme].clear()
    applyColorRuntimeOverrides()
    persist()
  }

  function setColorValue(
    definition: VisualColorTokenDefinition,
    value: string,
  ): boolean {
    if (!isAvailable) return false
    const normalized = normalizeVisualColorValue(value)
    if (!normalized) return false

    if (normalized === readColorBaseline(definition)) {
      colorOverrides[definition.theme].delete(definition.cssVar)
    } else {
      colorOverrides[definition.theme].set(definition.cssVar, normalized)
    }
    applyColorRuntimeOverrides()
    persist()
    return true
  }

  function resetColorValue(definition: VisualColorTokenDefinition): void {
    if (!isAvailable) return
    colorOverrides[definition.theme].delete(definition.cssVar)
    applyColorRuntimeOverrides()
    persist()
  }

  function resetColorTheme(theme: VisualColorTheme): void {
    if (!isAvailable) return
    colorOverrides[theme].clear()
    applyColorRuntimeOverrides()
    persist()
  }

  function resetAllColors(): void {
    if (!isAvailable) return
    for (const theme of visualColorThemes) colorOverrides[theme].clear()
    applyColorRuntimeOverrides()
    persist()
  }

  function restore(): void {
    if (!isAvailable || !root) return

    clearRuntimeDimensionOverrides()
    for (const theme of visualColorThemes) colorOverrides[theme].clear()
    applyColorRuntimeOverrides()
    if (!storage) return

    let rawValue: string | null
    try {
      rawValue = storage.getItem(VISUAL_TOKEN_TUNER_STORAGE_KEY)
    } catch {
      return
    }

    const overrides = parseStoredOverrides(rawValue, registry, colorRegistry)
    for (const definition of registry) {
      const stored = overrides.dimensions.get(definition.cssVar)
      if (stored === undefined || isDefaultValue(definition, stored)) continue
      root.style.setProperty(
        definition.cssVar,
        formatVisualTokenValue(stored, definition.unit),
      )
    }
    for (const theme of visualColorThemes) {
      for (const definition of colorRegistry) {
        if (definition.theme !== theme) continue
        const stored = overrides.colors[theme].get(definition.cssVar)
        if (!stored || stored === readColorBaseline(definition)) continue
        colorOverrides[theme].set(definition.cssVar, stored)
      }
    }
    applyColorRuntimeOverrides()

    if (rawValue && !hasDimensionOverrides() && !hasColorOverrides()) {
      try {
        storage.removeItem(VISUAL_TOKEN_TUNER_STORAGE_KEY)
      } catch {
        // 开发工具的临时保存失败不应影响真实页面预览。
      }
      return
    }

    if (hasDimensionOverrides() || hasColorOverrides()) persist()
  }

  function getDirtyDefinitions(): readonly VisualTokenDefinition[] {
    return registry.filter(
      (definition) => !isDefaultValue(definition, readValue(definition)),
    )
  }

  function getDirtyColorDefinitions(
    theme?: VisualColorTheme,
  ): readonly VisualColorTokenDefinition[] {
    return colorRegistry.filter(
      (definition) =>
        (!theme || definition.theme === theme) &&
        colorOverrides[definition.theme].has(definition.cssVar),
    )
  }

  function toCssVariables(): string {
    const lines = registry.map(
      (definition) =>
        `  ${definition.cssVar}: ${formatVisualTokenValue(
          readValue(definition),
          definition.unit,
        )};`,
    )
    return [':root {', ...lines, '}'].join('\n')
  }

  function toJson(): string {
    return JSON.stringify(
      Object.fromEntries(
        registry.map((definition) => [
          definition.cssVar,
          formatVisualTokenValue(readValue(definition), definition.unit),
        ]),
      ),
      null,
      2,
    )
  }

  function toColorCssVariables(): string {
    return visualColorThemes
      .map((theme) => {
        const lines = colorRegistry
          .filter((definition) => definition.theme === theme)
          .map(
            (definition) =>
              `  ${definition.cssVar}: ${readColorValue(definition)};`,
          )
        return [`:root[data-theme='${theme}'] {`, ...lines, '}'].join('\n')
      })
      .join('\n\n')
  }

  function toColorJson(): string {
    return JSON.stringify(readColorValues(), null, 2)
  }

  return {
    enabled: isAvailable,
    readValue,
    readValues,
    setValue,
    resetValue,
    resetAll,
    resetAllOverrides,
    readColorBaseline,
    readColorValue,
    readColorValues,
    setColorValue,
    resetColorValue,
    resetColorTheme,
    resetAllColors,
    restore,
    getDirtyDefinitions,
    getDirtyColorDefinitions,
    toCssVariables,
    toJson,
    toColorCssVariables,
    toColorJson,
  }
}

let hasInstalledVisualTokenTunerSync = false

export function initializeVisualTokenTuner(): void {
  const runtime = createVisualTokenTunerRuntime()
  runtime.restore()

  if (
    !runtime.enabled ||
    hasInstalledVisualTokenTunerSync ||
    typeof window === 'undefined'
  ) {
    return
  }

  window.addEventListener('storage', (event) => {
    if (event.key === VISUAL_TOKEN_TUNER_STORAGE_KEY) runtime.restore()
  })
  hasInstalledVisualTokenTunerSync = true
}
