<script setup lang="ts">
import {
  Button as VanButton,
  Tab as VanTab,
  Tabs as VanTabs,
  showToast,
} from 'vant'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  createVisualAppearanceTunerRuntime,
  createVisualTokenTunerRuntime,
  getVisualColorContrastRatio,
  type VisualAppearanceTokenDefinition,
  type VisualColorTheme,
  type VisualColorTokenDefinition,
  type VisualTokenDefinition,
  visualAppearanceTokenRegistry,
  visualAppearanceTokenTunerGroups,
  visualColorTokenRegistry,
  visualColorTokenTunerGroups,
  visualTokenRegistry,
  visualTokenTunerGroups,
} from './index'

type TunerMode = 'dimension' | 'color' | 'appearance'

const colorThemes = ['light', 'dark'] as const

const props = withDefaults(
  defineProps<{
    standalone?: boolean
  }>(),
  {
    standalone: false,
  },
)

const runtime = createVisualTokenTunerRuntime()
const appearanceRuntime = createVisualAppearanceTunerRuntime()
const enabled = runtime.enabled
const mode = ref<TunerMode>('dimension')
const activeGroup = ref(visualTokenTunerGroups[0].key)
const activeColorGroup = ref(visualColorTokenTunerGroups[0].key)
const activeAppearanceGroup = ref(visualAppearanceTokenTunerGroups[0].key)
const editingTheme = ref<VisualColorTheme>('light')
const editingAppearanceTheme = ref<VisualColorTheme>('light')
const searchText = ref('')
const values = ref(runtime.readValues())
const colorValues = ref(runtime.readColorValues())
const appearanceValues = ref(appearanceRuntime.readValues())
const invalidColorValues = ref<Record<string, string>>({})
const viewportWidth = ref(0)
const viewportHeight = ref(0)

const viewportLabel = computed(() => {
  if (viewportWidth.value < 375) return '小屏验证'
  if (viewportWidth.value <= 430) return '标准移动端'
  return '宽屏预览'
})
const dirtyDefinitions = computed(() => {
  void values.value
  return runtime.getDirtyDefinitions()
})
const dirtyColorDefinitions = computed(() => {
  void colorValues.value
  return runtime.getDirtyColorDefinitions()
})
const currentThemeDirtyDefinitions = computed(() => {
  void colorValues.value
  return runtime.getDirtyColorDefinitions(editingTheme.value)
})
const dirtyAppearanceDefinitions = computed(() => {
  void appearanceValues.value
  return appearanceRuntime.getDirtyDefinitions()
})
const currentAppearanceThemeDirtyDefinitions = computed(() => {
  void appearanceValues.value
  return appearanceRuntime.getDirtyDefinitions(editingAppearanceTheme.value)
})
const filteredDefinitions = computed(() => {
  const query = searchText.value.trim().toLocaleLowerCase()
  return visualTokenRegistry.filter((definition) => {
    if (!query) return definition.group === activeGroup.value
    return [definition.label, definition.cssVar, definition.description]
      .join(' ')
      .toLocaleLowerCase()
      .includes(query)
  })
})
const filteredColorDefinitions = computed(() => {
  const query = searchText.value.trim().toLocaleLowerCase()
  return visualColorTokenRegistry.filter((definition) => {
    if (definition.theme !== editingTheme.value) return false
    if (!query) return definition.group === activeColorGroup.value
    return [definition.label, definition.cssVar, definition.description]
      .join(' ')
      .toLocaleLowerCase()
      .includes(query)
  })
})
const filteredAppearanceDefinitions = computed(() => {
  const query = searchText.value.trim().toLocaleLowerCase()
  return visualAppearanceTokenRegistry.filter((definition) => {
    if (
      definition.group === 'shadow' &&
      definition.theme !== editingAppearanceTheme.value
    ) {
      return false
    }
    if (!query) return definition.group === activeAppearanceGroup.value
    return [definition.label, definition.cssVar, definition.description]
      .join(' ')
      .toLocaleLowerCase()
      .includes(query)
  })
})

function syncValues(): void {
  values.value = runtime.readValues()
  colorValues.value = runtime.readColorValues()
  appearanceValues.value = appearanceRuntime.readValues()
}

function updateViewport(): void {
  viewportWidth.value = window.innerWidth
  viewportHeight.value = window.innerHeight
}

function valueOf(definition: VisualTokenDefinition): number {
  return values.value[definition.key] ?? definition.defaultValue
}

function formatValue(definition: VisualTokenDefinition, value: number): string {
  return `${value}${definition.unit}`
}

function isDirty(definition: VisualTokenDefinition): boolean {
  return dirtyDefinitions.value.some((item) => item.key === definition.key)
}

function warningOf(definition: VisualTokenDefinition): string | null {
  return definition.warning?.(valueOf(definition)) ?? null
}

function applyValue(definition: VisualTokenDefinition, value: number): void {
  runtime.setValue(definition, value)
  syncValues()
}

function onRangeInput(definition: VisualTokenDefinition, event: Event): void {
  const value = Number((event.target as HTMLInputElement).value)
  applyValue(definition, value)
}

function onNumberInput(definition: VisualTokenDefinition, event: Event): void {
  const input = event.target as HTMLInputElement
  if (!Number.isFinite(input.valueAsNumber)) return
  applyValue(definition, input.valueAsNumber)
}

function resetItem(definition: VisualTokenDefinition): void {
  runtime.resetValue(definition)
  syncValues()
}

function appearanceValueOf(
  definition: VisualAppearanceTokenDefinition,
): number {
  return appearanceValues.value[definition.key] ?? definition.defaultValue
}

function formatAppearanceValue(
  definition: VisualAppearanceTokenDefinition,
  value: number,
): string {
  return `${value}${definition.unit}`
}

function isAppearanceDirty(
  definition: VisualAppearanceTokenDefinition,
): boolean {
  return dirtyAppearanceDefinitions.value.some(
    (item) => item.key === definition.key,
  )
}

function applyAppearanceValue(
  definition: VisualAppearanceTokenDefinition,
  value: number,
): void {
  appearanceRuntime.setValue(definition, value)
  syncValues()
}

function onAppearanceRangeInput(
  definition: VisualAppearanceTokenDefinition,
  event: Event,
): void {
  applyAppearanceValue(
    definition,
    Number((event.target as HTMLInputElement).value),
  )
}

function onAppearanceNumberInput(
  definition: VisualAppearanceTokenDefinition,
  event: Event,
): void {
  const input = event.target as HTMLInputElement
  if (!Number.isFinite(input.valueAsNumber)) return
  applyAppearanceValue(definition, input.valueAsNumber)
}

function resetAppearanceItem(
  definition: VisualAppearanceTokenDefinition,
): void {
  appearanceRuntime.resetValue(definition)
  syncValues()
}

function resetAppearanceGroup(): void {
  appearanceRuntime.resetGroup(
    activeAppearanceGroup.value,
    activeAppearanceGroup.value === 'shadow'
      ? editingAppearanceTheme.value
      : undefined,
  )
  syncValues()
}

function resetStage3BAppearance(): void {
  appearanceRuntime.resetAll()
  syncValues()
}

/** 只清理开发态 Override；不会改写任何已冻结的正式 Token 基线。 */
function resetAllTuning(): void {
  runtime.resetAllOverrides()
  appearanceRuntime.resetAll()
  syncValues()
}

function colorValueOf(definition: VisualColorTokenDefinition): string {
  return (
    colorValues.value[definition.theme]?.[definition.cssVar] ??
    runtime.readColorBaseline(definition)
  )
}

function isColorDirty(definition: VisualColorTokenDefinition): boolean {
  return colorValueOf(definition) !== runtime.readColorBaseline(definition)
}

function applyColorValue(
  definition: VisualColorTokenDefinition,
  nextValue: string,
): void {
  if (runtime.setColorValue(definition, nextValue)) {
    const remaining = { ...invalidColorValues.value }
    delete remaining[definition.key]
    invalidColorValues.value = remaining
    syncValues()
    return
  }
  invalidColorValues.value = {
    ...invalidColorValues.value,
    [definition.key]: '请输入 #RRGGBB 格式的颜色。',
  }
}

function onColorPickerInput(
  definition: VisualColorTokenDefinition,
  event: Event,
): void {
  applyColorValue(definition, (event.target as HTMLInputElement).value)
}

function onColorHexChange(
  definition: VisualColorTokenDefinition,
  event: Event,
): void {
  applyColorValue(definition, (event.target as HTMLInputElement).value)
}

function resetColorItem(definition: VisualColorTokenDefinition): void {
  runtime.resetColorValue(definition)
  syncValues()
}

function resetColorTheme(): void {
  runtime.resetColorTheme(editingTheme.value)
  syncValues()
}

function resetAllColors(): void {
  runtime.resetAllColors()
  syncValues()
}

function colorContrastWarning(
  definition: VisualColorTokenDefinition,
): string | null {
  if (!definition.contrastTarget) return null
  const target = visualColorTokenRegistry.find(
    (item) =>
      item.theme === definition.theme &&
      item.cssVar === definition.contrastTarget?.cssVar,
  )
  if (!target) return null
  const ratio = getVisualColorContrastRatio(
    colorValueOf(definition),
    colorValueOf(target),
  )
  if (ratio === null || ratio >= definition.contrastTarget.minimumRatio) {
    return null
  }
  return `与 ${definition.contrastTarget.label} 的对比度 ${ratio.toFixed(2)}:1，低于 ${definition.contrastTarget.minimumRatio}:1。`
}

function closeStandaloneTuner(): void {
  window.close()
}

async function copyText(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }

  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.append(textarea)
  textarea.select()
  const copied = document.execCommand('copy')
  textarea.remove()
  if (!copied) throw new Error('无法写入剪贴板')
}

async function copyCssVariables(): Promise<void> {
  try {
    await copyText(runtime.toCssVariables())
    showToast('已复制尺寸 CSS')
  } catch {
    showToast('复制失败')
  }
}

async function copyJson(): Promise<void> {
  try {
    await copyText(runtime.toJson())
    showToast('已复制尺寸 JSON')
  } catch {
    showToast('复制失败')
  }
}

async function copyColorCssVariables(): Promise<void> {
  try {
    await copyText(runtime.toColorCssVariables())
    showToast('已复制颜色 CSS')
  } catch {
    showToast('复制失败')
  }
}

async function copyColorJson(): Promise<void> {
  try {
    await copyText(runtime.toColorJson())
    showToast('已复制颜色 JSON')
  } catch {
    showToast('复制失败')
  }
}

async function copyAppearanceCssVariables(): Promise<void> {
  try {
    await copyText(appearanceRuntime.toCssVariables())
    showToast('已复制外观 CSS')
  } catch {
    showToast('复制失败')
  }
}

async function copyAppearanceJson(): Promise<void> {
  try {
    await copyText(appearanceRuntime.toJson())
    showToast('已复制外观 JSON')
  } catch {
    showToast('复制失败')
  }
}

onMounted(() => {
  if (!enabled) return
  runtime.restore()
  appearanceRuntime.restore()
  syncValues()
  updateViewport()
  window.addEventListener('resize', updateViewport)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateViewport)
})
</script>

<template>
  <div
    v-if="enabled"
    class="visual-token-tuner"
    :class="{ 'visual-token-tuner--standalone': props.standalone }"
  >
    <a
      v-if="!props.standalone"
      class="visual-token-tuner__entry mobile-icon-button mobile-pressable"
      href="#/__visual-tuner"
      target="_blank"
      rel="noopener"
      aria-label="在独立窗口打开视觉 Token 调参器"
      data-testid="visual-token-tuner-entry"
    >
      <span class="visual-token-tuner__entry-label">调参</span>
    </a>

    <section
      v-else
      class="visual-token-tuner__panel visual-token-tuner__panel--standalone"
      data-testid="visual-token-tuner-panel"
      aria-label="视觉 Token 调参器"
    >
      <div class="visual-token-tuner__content">
        <header class="visual-token-tuner__header">
          <div class="visual-token-tuner__title-block">
            <strong>视觉 Token 调参 V3</strong>
            <span>
              尺寸已调整 {{ dirtyDefinitions.length }} 项 · 颜色已调整
              {{ dirtyColorDefinitions.length }} 项 · 外观已调整
              {{ dirtyAppearanceDefinitions.length }} 项 · {{ viewportWidth }} ×
              {{ viewportHeight }} · {{ viewportLabel }}
            </span>
          </div>
          <button
            class="visual-token-tuner__close mobile-icon-button mobile-pressable"
            type="button"
            aria-label="关闭调参窗口"
            data-testid="visual-token-tuner-close"
            @click="closeStandaloneTuner"
          >
            <span aria-hidden="true">×</span>
          </button>
        </header>

        <div
          class="visual-token-tuner__mode-switch"
          role="tablist"
          aria-label="调参类别"
        >
          <button
            class="visual-token-tuner__switch-button"
            :class="{
              'visual-token-tuner__switch-button--active': mode === 'dimension',
            }"
            type="button"
            role="tab"
            :aria-selected="mode === 'dimension'"
            data-testid="visual-token-tuner-mode-dimension"
            @click="mode = 'dimension'"
          >
            尺寸
          </button>
          <button
            class="visual-token-tuner__switch-button"
            :class="{
              'visual-token-tuner__switch-button--active': mode === 'color',
            }"
            type="button"
            role="tab"
            :aria-selected="mode === 'color'"
            data-testid="visual-token-tuner-mode-color"
            @click="mode = 'color'"
          >
            颜色
          </button>
          <button
            class="visual-token-tuner__switch-button"
            :class="{
              'visual-token-tuner__switch-button--active':
                mode === 'appearance',
            }"
            type="button"
            role="tab"
            :aria-selected="mode === 'appearance'"
            data-testid="visual-token-tuner-mode-appearance"
            @click="mode = 'appearance'"
          >
            外观
          </button>
        </div>

        <label class="visual-token-tuner__search">
          <span>搜索参数</span>
          <input
            v-model="searchText"
            type="search"
            placeholder="例如：图标、表面、状态"
            data-testid="visual-token-tuner-search"
          />
        </label>

        <template v-if="mode === 'dimension'">
          <VanTabs
            v-model:active="activeGroup"
            class="visual-token-tuner__tabs"
          >
            <VanTab
              v-for="group in visualTokenTunerGroups"
              :key="group.key"
              :name="group.key"
              :title="group.label"
            />
          </VanTabs>

          <div class="visual-token-tuner__parameters">
            <p class="visual-token-tuner__group-description">
              {{
                searchText.trim()
                  ? `找到 ${filteredDefinitions.length} 项参数`
                  : visualTokenTunerGroups.find(
                      (group) => group.key === activeGroup,
                    )?.description
              }}
            </p>

            <p
              v-if="filteredDefinitions.length === 0"
              class="visual-token-tuner__empty"
            >
              没有匹配的参数
            </p>

            <article
              v-for="definition in filteredDefinitions"
              :key="definition.key"
              class="visual-token-tuner__parameter"
              :data-testid="`visual-token-${definition.key}`"
            >
              <div class="visual-token-tuner__parameter-heading">
                <label :for="`visual-token-number-${definition.key}`">
                  {{ definition.label }}
                </label>
                <span v-if="isDirty(definition)">已修改</span>
              </div>
              <p>{{ definition.description }}</p>

              <div class="visual-token-tuner__control-row">
                <input
                  :id="`visual-token-range-${definition.key}`"
                  :aria-label="`${definition.label}滑块`"
                  :value="valueOf(definition)"
                  :min="definition.min"
                  :max="definition.max"
                  :step="definition.step"
                  type="range"
                  :data-testid="`visual-token-range-${definition.key}`"
                  @input="onRangeInput(definition, $event)"
                />
                <input
                  :id="`visual-token-number-${definition.key}`"
                  :aria-label="`${definition.label}数值输入`"
                  :value="valueOf(definition)"
                  :min="definition.min"
                  :max="definition.max"
                  :step="definition.step"
                  type="number"
                  inputmode="decimal"
                  :data-testid="`visual-token-number-${definition.key}`"
                  @input="onNumberInput(definition, $event)"
                />
                <span class="visual-token-tuner__unit">
                  {{ definition.unit || '—' }}
                </span>
                <VanButton
                  size="small"
                  plain
                  :disabled="!isDirty(definition)"
                  :data-testid="`visual-token-reset-${definition.key}`"
                  @click="resetItem(definition)"
                >
                  恢复
                </VanButton>
              </div>

              <div class="visual-token-tuner__value-summary">
                <span
                  >默认
                  {{ formatValue(definition, definition.defaultValue) }}</span
                >
                <span
                  >当前 {{ formatValue(definition, valueOf(definition)) }}</span
                >
              </div>
              <p
                v-if="warningOf(definition)"
                class="visual-token-tuner__warning"
              >
                {{ warningOf(definition) }}
              </p>
            </article>
          </div>

          <footer class="visual-token-tuner__footer">
            <VanButton
              plain
              :disabled="
                dirtyDefinitions.length === 0 &&
                dirtyColorDefinitions.length === 0 &&
                dirtyAppearanceDefinitions.length === 0
              "
              data-testid="visual-token-tuner-reset-all"
              @click="resetAllTuning"
            >
              恢复全部调参
            </VanButton>
            <VanButton
              plain
              data-testid="visual-token-tuner-copy-css"
              @click="copyCssVariables"
            >
              复制尺寸 CSS
            </VanButton>
            <VanButton
              plain
              data-testid="visual-token-tuner-copy-json"
              @click="copyJson"
            >
              复制尺寸 JSON
            </VanButton>
          </footer>
        </template>

        <template v-else-if="mode === 'color'">
          <div
            class="visual-token-tuner__theme-context"
            role="tablist"
            aria-label="颜色编辑主题"
          >
            <button
              v-for="theme in colorThemes"
              :key="theme"
              class="visual-token-tuner__switch-button"
              :class="{
                'visual-token-tuner__switch-button--active':
                  editingTheme === theme,
              }"
              type="button"
              role="tab"
              :aria-selected="editingTheme === theme"
              :data-testid="`visual-token-tuner-theme-${theme}`"
              @click="editingTheme = theme"
            >
              {{ theme === 'light' ? '编辑浅色' : '编辑深色' }}
            </button>
          </div>

          <VanTabs
            v-model:active="activeColorGroup"
            class="visual-token-tuner__tabs"
          >
            <VanTab
              v-for="group in visualColorTokenTunerGroups"
              :key="group.key"
              :name="group.key"
              :title="group.label"
            />
          </VanTabs>

          <div class="visual-token-tuner__parameters">
            <p class="visual-token-tuner__group-description">
              {{
                searchText.trim()
                  ? `找到 ${filteredColorDefinitions.length} 项颜色参数`
                  : visualColorTokenTunerGroups.find(
                      (group) => group.key === activeColorGroup,
                    )?.description
              }}
            </p>
            <p class="visual-token-tuner__theme-note">
              当前仅编辑{{ editingTheme === 'light' ? '浅色' : '深色' }}
              Token；不会修改产品主题设置。
            </p>

            <p
              v-if="filteredColorDefinitions.length === 0"
              class="visual-token-tuner__empty"
            >
              没有匹配的颜色参数
            </p>

            <article
              v-for="definition in filteredColorDefinitions"
              :key="definition.key"
              class="visual-token-tuner__parameter"
              :data-testid="`visual-token-color-${definition.key}`"
            >
              <div class="visual-token-tuner__parameter-heading">
                <label :for="`visual-token-color-text-${definition.key}`">
                  {{ definition.label }}
                </label>
                <span v-if="isColorDirty(definition)">已修改</span>
              </div>
              <p>{{ definition.description }}</p>

              <div class="visual-token-tuner__color-control-row">
                <input
                  :id="`visual-token-color-picker-${definition.key}`"
                  :aria-label="`${definition.label}颜色选择`"
                  :value="colorValueOf(definition)"
                  type="color"
                  :data-testid="`visual-token-color-picker-${definition.key}`"
                  @input="onColorPickerInput(definition, $event)"
                />
                <input
                  :id="`visual-token-color-text-${definition.key}`"
                  :aria-label="`${definition.label}十六进制颜色`"
                  :value="colorValueOf(definition)"
                  type="text"
                  inputmode="text"
                  spellcheck="false"
                  :data-testid="`visual-token-color-hex-${definition.key}`"
                  @change="onColorHexChange(definition, $event)"
                />
                <VanButton
                  size="small"
                  plain
                  :disabled="!isColorDirty(definition)"
                  :data-testid="`visual-token-color-reset-${definition.key}`"
                  @click="resetColorItem(definition)"
                >
                  恢复
                </VanButton>
              </div>

              <div class="visual-token-tuner__value-summary">
                <span>默认 {{ runtime.readColorBaseline(definition) }}</span>
                <span>当前 {{ colorValueOf(definition) }}</span>
              </div>
              <p
                v-if="invalidColorValues[definition.key]"
                class="visual-token-tuner__warning"
              >
                {{ invalidColorValues[definition.key] }}
              </p>
              <p
                v-else-if="colorContrastWarning(definition)"
                class="visual-token-tuner__warning"
              >
                {{ colorContrastWarning(definition) }}
              </p>
            </article>
          </div>

          <footer
            class="visual-token-tuner__footer visual-token-tuner__footer--color"
          >
            <VanButton
              plain
              :disabled="currentThemeDirtyDefinitions.length === 0"
              data-testid="visual-token-tuner-reset-color-theme"
              @click="resetColorTheme"
            >
              恢复本主题
            </VanButton>
            <VanButton
              plain
              :disabled="dirtyColorDefinitions.length === 0"
              data-testid="visual-token-tuner-reset-all-colors"
              @click="resetAllColors"
            >
              恢复全部颜色
            </VanButton>
            <VanButton
              plain
              data-testid="visual-token-tuner-copy-color-css"
              @click="copyColorCssVariables"
            >
              复制颜色 CSS
            </VanButton>
            <VanButton
              plain
              data-testid="visual-token-tuner-copy-color-json"
              @click="copyColorJson"
            >
              复制颜色 JSON
            </VanButton>
            <VanButton
              plain
              :disabled="
                dirtyDefinitions.length === 0 &&
                dirtyColorDefinitions.length === 0 &&
                dirtyAppearanceDefinitions.length === 0
              "
              data-testid="visual-token-tuner-reset-all"
              @click="resetAllTuning"
            >
              恢复全部调参
            </VanButton>
          </footer>
        </template>

        <template v-else>
          <div
            v-if="activeAppearanceGroup === 'shadow'"
            class="visual-token-tuner__theme-context"
            role="tablist"
            aria-label="阴影编辑主题"
          >
            <button
              v-for="theme in colorThemes"
              :key="theme"
              class="visual-token-tuner__switch-button"
              :class="{
                'visual-token-tuner__switch-button--active':
                  editingAppearanceTheme === theme,
              }"
              type="button"
              role="tab"
              :aria-selected="editingAppearanceTheme === theme"
              :data-testid="`visual-token-tuner-appearance-theme-${theme}`"
              @click="editingAppearanceTheme = theme"
            >
              {{ theme === 'light' ? '编辑浅色阴影' : '编辑深色阴影' }}
            </button>
          </div>

          <VanTabs
            v-model:active="activeAppearanceGroup"
            class="visual-token-tuner__tabs"
          >
            <VanTab
              v-for="group in visualAppearanceTokenTunerGroups"
              :key="group.key"
              :name="group.key"
              :title="group.label"
            />
          </VanTabs>

          <div class="visual-token-tuner__parameters">
            <p class="visual-token-tuner__group-description">
              {{
                searchText.trim()
                  ? `找到 ${filteredAppearanceDefinitions.length} 项外观参数`
                  : visualAppearanceTokenTunerGroups.find(
                      (group) => group.key === activeAppearanceGroup,
                    )?.description
              }}
            </p>
            <p
              v-if="activeAppearanceGroup === 'shadow'"
              class="visual-token-tuner__theme-note"
            >
              当前仅编辑{{
                editingAppearanceTheme === 'light' ? '浅色' : '深色'
              }}阴影；不会修改产品主题设置。
            </p>

            <p
              v-if="filteredAppearanceDefinitions.length === 0"
              class="visual-token-tuner__empty"
            >
              没有匹配的参数
            </p>

            <article
              v-for="definition in filteredAppearanceDefinitions"
              :key="definition.key"
              class="visual-token-tuner__parameter"
              :data-testid="`visual-token-appearance-${definition.key}`"
            >
              <div class="visual-token-tuner__parameter-heading">
                <label
                  :for="`visual-token-appearance-number-${definition.key}`"
                >
                  {{ definition.label }}
                </label>
                <span v-if="isAppearanceDirty(definition)">已修改</span>
              </div>
              <p>{{ definition.description }}</p>

              <div class="visual-token-tuner__control-row">
                <input
                  :id="`visual-token-appearance-range-${definition.key}`"
                  :aria-label="`${definition.label}滑块`"
                  :value="appearanceValueOf(definition)"
                  :min="definition.min"
                  :max="definition.max"
                  :step="definition.step"
                  type="range"
                  :data-testid="`visual-token-appearance-range-${definition.key}`"
                  @input="onAppearanceRangeInput(definition, $event)"
                />
                <input
                  :id="`visual-token-appearance-number-${definition.key}`"
                  :aria-label="`${definition.label}数值输入`"
                  :value="appearanceValueOf(definition)"
                  :min="definition.min"
                  :max="definition.max"
                  :step="definition.step"
                  type="number"
                  inputmode="decimal"
                  :data-testid="`visual-token-appearance-number-${definition.key}`"
                  @input="onAppearanceNumberInput(definition, $event)"
                />
                <span class="visual-token-tuner__unit">
                  {{ definition.unit || '—' }}
                </span>
                <VanButton
                  size="small"
                  plain
                  :disabled="!isAppearanceDirty(definition)"
                  :data-testid="`visual-token-appearance-reset-${definition.key}`"
                  @click="resetAppearanceItem(definition)"
                >
                  恢复
                </VanButton>
              </div>

              <div class="visual-token-tuner__value-summary">
                <span>
                  默认
                  {{
                    formatAppearanceValue(
                      definition,
                      appearanceRuntime.readBaseline(definition),
                    )
                  }}
                </span>
                <span>
                  当前
                  {{
                    formatAppearanceValue(
                      definition,
                      appearanceValueOf(definition),
                    )
                  }}
                </span>
              </div>
            </article>
          </div>

          <footer
            class="visual-token-tuner__footer visual-token-tuner__footer--appearance"
          >
            <VanButton
              plain
              :disabled="
                activeAppearanceGroup === 'shadow'
                  ? currentAppearanceThemeDirtyDefinitions.length === 0
                  : !dirtyAppearanceDefinitions.some(
                      (item) => item.group === activeAppearanceGroup,
                    )
              "
              data-testid="visual-token-tuner-reset-appearance-group"
              @click="resetAppearanceGroup"
            >
              恢复本组
            </VanButton>
            <VanButton
              plain
              :disabled="dirtyAppearanceDefinitions.length === 0"
              data-testid="visual-token-tuner-reset-stage3b"
              @click="resetStage3BAppearance"
            >
              恢复 Stage 3B
            </VanButton>
            <VanButton
              plain
              data-testid="visual-token-tuner-copy-appearance-css"
              @click="copyAppearanceCssVariables"
            >
              复制外观 CSS
            </VanButton>
            <VanButton
              plain
              data-testid="visual-token-tuner-copy-appearance-json"
              @click="copyAppearanceJson"
            >
              复制外观 JSON
            </VanButton>
            <VanButton
              plain
              :disabled="
                dirtyDefinitions.length === 0 &&
                dirtyColorDefinitions.length === 0 &&
                dirtyAppearanceDefinitions.length === 0
              "
              data-testid="visual-token-tuner-reset-all"
              @click="resetAllTuning"
            >
              恢复全部调参
            </VanButton>
          </footer>
        </template>
      </div>
    </section>
  </div>
</template>

<style>
.visual-token-tuner {
  position: fixed;
  right: max(var(--space-3), var(--safe-area-right));
  bottom: max(var(--space-3), var(--safe-area-bottom));
  z-index: 3001;
}

@media (max-width: 768px) {
  .visual-token-tuner {
    bottom: calc(
      var(--layout-bottom-nav-height) +
        max(var(--space-3), var(--safe-area-bottom))
    );
  }
}

.visual-token-tuner--standalone {
  position: static;
  display: block;
  min-height: 100dvh;
  padding-top: var(--safe-area-top);
}

.visual-token-tuner__entry {
  color: var(--color-primary);
  text-decoration: none;
}

.visual-token-tuner__entry-label {
  position: relative;
  z-index: 1;
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
  line-height: var(--line-height-caption);
}

.visual-token-tuner__panel {
  display: flex;
  max-width: 100%;
  color: var(--text-primary);
  background: var(--bg-surface-raised);
}

.visual-token-tuner__panel--standalone {
  width: min(100%, 480px);
  min-height: calc(100dvh - var(--safe-area-top));
  margin-inline: auto;
}

.visual-token-tuner__content {
  display: grid;
  width: 100%;
  min-width: 0;
  min-height: 0;
  grid-template-rows: auto auto auto auto minmax(0, 1fr) auto;
}

.visual-token-tuner__header {
  display: flex;
  min-width: 0;
  padding: var(--layout-content-gap) var(--space-3);
  gap: var(--layout-content-gap);
  align-items: center;
  justify-content: space-between;
  border-bottom: var(--border-width) solid var(--border-divider);
}

.visual-token-tuner__title-block {
  display: grid;
  min-width: 0;
  gap: var(--layout-compact-gap);
}

.visual-token-tuner__title-block strong {
  font-size: var(--font-size-label);
  line-height: var(--line-height-label);
}

.visual-token-tuner__title-block span,
.visual-token-tuner__group-description,
.visual-token-tuner__theme-note,
.visual-token-tuner__parameter > p,
.visual-token-tuner__value-summary,
.visual-token-tuner__warning,
.visual-token-tuner__empty {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

.visual-token-tuner__close {
  flex: none;
  font-size: var(--font-size-title);
}

.visual-token-tuner__mode-switch,
.visual-token-tuner__theme-context {
  display: grid;
  padding: var(--layout-content-gap) var(--space-3) 0;
  gap: var(--layout-compact-gap);
}

.visual-token-tuner__mode-switch {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.visual-token-tuner__theme-context {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.visual-token-tuner__switch-button {
  min-height: var(--touch-target-min);
  padding: 0 var(--layout-content-gap);
  color: var(--text-secondary);
  font-size: var(--font-size-action);
  font-weight: var(--font-weight-medium);
  line-height: var(--line-height-action);
  background: var(--bg-control);
  border: var(--border-width) solid var(--border-divider);
  border-radius: var(--radius-control);
}

.visual-token-tuner__switch-button--active {
  color: var(--text-selected);
  background: var(--bg-selected);
  border-color: var(--color-primary);
}

.visual-token-tuner__search {
  display: grid;
  padding: var(--layout-content-gap) var(--space-3);
  gap: var(--layout-compact-gap);
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

.visual-token-tuner__search input,
.visual-token-tuner__control-row input[type='number'],
.visual-token-tuner__color-control-row input[type='text'] {
  min-width: 0;
  height: var(--control-height-compact);
  padding-inline: var(--layout-content-gap);
  color: var(--text-primary);
  background: var(--bg-control);
  border: var(--border-width) solid var(--border-divider);
  border-radius: var(--radius-control);
}

.visual-token-tuner__tabs {
  min-width: 0;
  border-bottom: var(--border-width) solid var(--border-divider);
}

.visual-token-tuner__parameters {
  min-width: 0;
  padding: var(--layout-content-gap) var(--space-3);
  overflow-x: hidden;
  overflow-y: auto;
}

.visual-token-tuner__theme-note {
  margin-top: var(--layout-compact-gap);
  color: var(--text-muted);
}

.visual-token-tuner__parameter {
  display: grid;
  min-width: 0;
  padding-block: var(--space-3);
  gap: var(--layout-compact-gap);
  border-bottom: var(--border-width) solid var(--border-divider);
}

.visual-token-tuner__parameter:first-of-type {
  padding-top: var(--layout-compact-gap);
}

.visual-token-tuner__parameter-heading {
  display: flex;
  min-width: 0;
  gap: var(--layout-content-gap);
  align-items: center;
  justify-content: space-between;
}

.visual-token-tuner__parameter-heading label {
  min-width: 0;
  overflow: hidden;
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-medium);
  line-height: var(--line-height-body);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.visual-token-tuner__parameter-heading span {
  flex: none;
  color: var(--color-primary);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

.visual-token-tuner__control-row {
  display: grid;
  min-width: 0;
  grid-template-columns: minmax(0, 1fr) 58px 20px auto;
  gap: var(--layout-compact-gap);
  align-items: center;
}

.visual-token-tuner__control-row input[type='range'] {
  width: 100%;
  min-width: 0;
  accent-color: var(--color-primary);
}

.visual-token-tuner__color-control-row {
  display: grid;
  min-width: 0;
  grid-template-columns: var(--touch-target-min) minmax(0, 1fr) auto;
  gap: var(--layout-compact-gap);
  align-items: center;
}

.visual-token-tuner__color-control-row input[type='color'] {
  width: var(--touch-target-min);
  min-width: var(--touch-target-min);
  height: var(--touch-target-min);
  padding: var(--layout-compact-gap);
  cursor: pointer;
  background: var(--bg-control);
  border: var(--border-width) solid var(--border-divider);
  border-radius: var(--radius-control);
}

.visual-token-tuner__unit {
  color: var(--text-muted);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
  text-align: center;
}

.visual-token-tuner__control-row .van-button,
.visual-token-tuner__color-control-row .van-button {
  min-width: var(--touch-target-min);
}

.visual-token-tuner__value-summary {
  display: flex;
  gap: var(--layout-content-gap);
  justify-content: space-between;
}

.visual-token-tuner__warning {
  color: var(--status-warning);
}

.visual-token-tuner__footer {
  display: grid;
  padding: var(--layout-content-gap) var(--space-3)
    max(var(--layout-content-gap), var(--safe-area-bottom));
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--layout-compact-gap);
  border-top: var(--border-width) solid var(--border-divider);
}

.visual-token-tuner__footer--color {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.visual-token-tuner__footer--appearance {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.visual-token-tuner__footer .van-button {
  min-width: 0;
  padding-inline: var(--layout-compact-gap);
}
</style>
