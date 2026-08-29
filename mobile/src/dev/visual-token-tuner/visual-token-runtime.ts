import {
  type VisualTokenDefinition,
  type VisualTokenUnit,
  visualTokenRegistry,
} from './visual-token-registry'

export const VISUAL_TOKEN_TUNER_STORAGE_KEY =
  'control-center.mobile.visual-token-tuner-v1'

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
  root?: HTMLElement | null
  storage?: VisualTokenStorage | null
  getComputedStyle?: (element: Element) => CSSStyleDeclaration
}

export type VisualTokenValues = Record<string, number>

export function isVisualTokenTunerEnabled(
  environment: VisualTokenTunerEnvironment = import.meta.env,
): boolean {
  return Boolean(environment.DEV) && environment.VITE_VISUAL_TUNER !== 'false'
}

function getDefaultRoot(): HTMLElement | null {
  if (typeof document === 'undefined') return null
  return document.documentElement
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

function isDefaultValue(
  definition: VisualTokenDefinition,
  value: number,
): boolean {
  return Math.abs(value - definition.defaultValue) < 0.0001
}

function parseStoredOverrides(
  rawValue: string | null,
  registry: readonly VisualTokenDefinition[],
): Map<string, number> {
  if (!rawValue) return new Map()

  try {
    const payload: unknown = JSON.parse(rawValue)
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
      return new Map()
    }

    const values = payload as Record<string, unknown>
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
  } catch {
    return new Map()
  }
}

export interface VisualTokenTunerRuntime {
  readonly enabled: boolean
  readValue(definition: VisualTokenDefinition): number
  readValues(): VisualTokenValues
  setValue(definition: VisualTokenDefinition, value: number): void
  resetValue(definition: VisualTokenDefinition): void
  resetAll(): void
  restore(): void
  getDirtyDefinitions(): readonly VisualTokenDefinition[]
  toCssVariables(): string
  toJson(): string
}

export function createVisualTokenTunerRuntime(
  options: VisualTokenRuntimeOptions = {},
): VisualTokenTunerRuntime {
  const enabled = options.enabled ?? isVisualTokenTunerEnabled()
  const registry = options.registry ?? visualTokenRegistry
  const root = options.root ?? getDefaultRoot()
  const storage = enabled
    ? options.storage === undefined
      ? getDefaultStorage()
      : options.storage
    : null
  const readComputedStyle = options.getComputedStyle ?? getDefaultComputedStyle
  const isAvailable = enabled && Boolean(root)

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

  function persist(): void {
    if (!isAvailable || !storage) return

    const overrides = Object.fromEntries(
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

    try {
      if (Object.keys(overrides).length === 0) {
        storage.removeItem(VISUAL_TOKEN_TUNER_STORAGE_KEY)
        return
      }
      storage.setItem(VISUAL_TOKEN_TUNER_STORAGE_KEY, JSON.stringify(overrides))
    } catch {
      // 开发工具的临时保存失败不应影响真实页面预览。
    }
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
    for (const definition of registry) {
      root.style.removeProperty(definition.cssVar)
    }
    try {
      storage?.removeItem(VISUAL_TOKEN_TUNER_STORAGE_KEY)
    } catch {
      // 开发工具的临时保存失败不应影响真实页面预览。
    }
  }

  function restore(): void {
    if (!isAvailable || !root || !storage) return

    let rawValue: string | null
    try {
      rawValue = storage.getItem(VISUAL_TOKEN_TUNER_STORAGE_KEY)
    } catch {
      return
    }

    const overrides = parseStoredOverrides(rawValue, registry)
    for (const definition of registry) {
      const stored = overrides.get(definition.cssVar)
      if (stored === undefined || isDefaultValue(definition, stored)) continue
      root.style.setProperty(
        definition.cssVar,
        formatVisualTokenValue(stored, definition.unit),
      )
    }
  }

  function getDirtyDefinitions(): readonly VisualTokenDefinition[] {
    return registry.filter(
      (definition) => !isDefaultValue(definition, readValue(definition)),
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

  return {
    enabled: isAvailable,
    readValue,
    readValues,
    setValue,
    resetValue,
    resetAll,
    restore,
    getDirtyDefinitions,
    toCssVariables,
    toJson,
  }
}

export function initializeVisualTokenTuner(): void {
  const runtime = createVisualTokenTunerRuntime()
  runtime.restore()
}
