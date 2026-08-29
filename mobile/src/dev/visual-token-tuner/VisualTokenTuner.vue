<script setup lang="ts">
import {
  Button as VanButton,
  Tab as VanTab,
  Tabs as VanTabs,
  showToast,
} from 'vant'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  createVisualTokenTunerRuntime,
  type VisualTokenDefinition,
  visualTokenRegistry,
  visualTokenTunerGroups,
} from './index'

const props = withDefaults(
  defineProps<{
    standalone?: boolean
  }>(),
  {
    standalone: false,
  },
)

const runtime = createVisualTokenTunerRuntime()
const enabled = runtime.enabled
const activeGroup = ref(visualTokenTunerGroups[0].key)
const searchText = ref('')
const values = ref(runtime.readValues())
const viewportWidth = ref(0)
const viewportHeight = ref(0)

const viewportLabel = computed(() => {
  if (viewportWidth.value < 375) return '小屏验证'
  if (viewportWidth.value <= 430) return '标准移动端'
  return '宽屏预览'
})
const dirtyDefinitions = computed(() =>
  visualTokenRegistry.filter(
    (definition) =>
      Math.abs(valueOf(definition) - definition.defaultValue) >= 0.0001,
  ),
)
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

function syncValues(): void {
  values.value = runtime.readValues()
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

function resetAll(): void {
  runtime.resetAll()
  syncValues()
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
    showToast('已复制 CSS 变量')
  } catch {
    showToast('复制失败')
  }
}

async function copyJson(): Promise<void> {
  try {
    await copyText(runtime.toJson())
    showToast('已复制 JSON')
  } catch {
    showToast('复制失败')
  }
}

onMounted(() => {
  if (!enabled) return
  runtime.restore()
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
            <strong>视觉 Token 调参</strong>
            <span>
              已调整 {{ dirtyDefinitions.length }} 项 · {{ viewportWidth }} ×
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

        <label class="visual-token-tuner__search">
          <span>搜索参数</span>
          <input
            v-model="searchText"
            type="search"
            placeholder="例如：图标、内边距、能力"
            data-testid="visual-token-tuner-search"
          />
        </label>

        <VanTabs v-model:active="activeGroup" class="visual-token-tuner__tabs">
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
            <p v-if="warningOf(definition)" class="visual-token-tuner__warning">
              {{ warningOf(definition) }}
            </p>
          </article>
        </div>

        <footer class="visual-token-tuner__footer">
          <VanButton
            plain
            :disabled="dirtyDefinitions.length === 0"
            data-testid="visual-token-tuner-reset-all"
            @click="resetAll"
          >
            恢复全部
          </VanButton>
          <VanButton
            plain
            data-testid="visual-token-tuner-copy-css"
            @click="copyCssVariables"
          >
            复制 CSS
          </VanButton>
          <VanButton
            plain
            data-testid="visual-token-tuner-copy-json"
            @click="copyJson"
          >
            复制 JSON
          </VanButton>
        </footer>
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
  grid-template-rows: auto auto auto minmax(0, 1fr) auto;
}

.visual-token-tuner__header {
  display: flex;
  min-width: 0;
  padding: var(--space-2) var(--space-3);
  gap: var(--space-2);
  align-items: center;
  justify-content: space-between;
  border-bottom: var(--border-width) solid var(--border-subtle);
}

.visual-token-tuner__title-block {
  display: grid;
  min-width: 0;
  gap: var(--space-1);
}

.visual-token-tuner__title-block strong {
  font-size: var(--font-size-label);
  line-height: var(--line-height-label);
}

.visual-token-tuner__title-block span,
.visual-token-tuner__group-description,
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

.visual-token-tuner__search {
  display: grid;
  padding: var(--space-2) var(--space-3);
  gap: var(--space-1);
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

.visual-token-tuner__search input,
.visual-token-tuner__control-row input[type='number'] {
  min-width: 0;
  height: var(--control-height-compact);
  padding-inline: var(--space-2);
  color: var(--text-primary);
  background: var(--bg-subtle);
  border: var(--border-width) solid var(--border-subtle);
  border-radius: var(--radius-control);
}

.visual-token-tuner__tabs {
  min-width: 0;
  border-bottom: var(--border-width) solid var(--border-subtle);
}

.visual-token-tuner__parameters {
  min-width: 0;
  padding: var(--space-2) var(--space-3);
  overflow-x: hidden;
  overflow-y: auto;
}

.visual-token-tuner__parameter {
  display: grid;
  min-width: 0;
  padding-block: var(--space-3);
  gap: var(--space-1);
  border-bottom: var(--border-width) solid var(--border-subtle);
}

.visual-token-tuner__parameter:first-of-type {
  padding-top: var(--space-1);
}

.visual-token-tuner__parameter-heading {
  display: flex;
  min-width: 0;
  gap: var(--space-2);
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
  gap: var(--space-1);
  align-items: center;
}

.visual-token-tuner__control-row input[type='range'] {
  width: 100%;
  min-width: 0;
  accent-color: var(--color-primary);
}

.visual-token-tuner__unit {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
  text-align: center;
}

.visual-token-tuner__control-row .van-button {
  min-width: var(--touch-target-min);
}

.visual-token-tuner__value-summary {
  display: flex;
  gap: var(--space-2);
  justify-content: space-between;
}

.visual-token-tuner__warning {
  color: var(--status-warning);
}

.visual-token-tuner__footer {
  display: grid;
  padding: var(--space-2) var(--space-3)
    max(var(--space-2), var(--safe-area-bottom));
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-1);
  border-top: var(--border-width) solid var(--border-subtle);
}

.visual-token-tuner__footer .van-button {
  min-width: 0;
  padding-inline: var(--space-1);
}
</style>
