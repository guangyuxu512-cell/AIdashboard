<script setup lang="ts">
import { storeToRefs } from 'pinia'
import {
  Button as VanButton,
  Cell as VanCell,
  CellGroup as VanCellGroup,
  Field as VanField,
  NoticeBar as VanNoticeBar,
  Popup as VanPopup,
  Tag as VanTag,
} from 'vant'
import { computed, ref } from 'vue'

import { useThemeStore, type ThemeMode } from '@/app/stores/theme'
import { AppPage } from '@/shared/ui'

const themeStore = useThemeStore()
const { mode, resolvedTheme } = storeToRefs(themeStore)
const fieldValue = ref('')
const sheetVisible = ref(false)

const themeOptions: ReadonlyArray<{ label: string; value: ThemeMode }> = [
  { label: '浅色', value: 'light' },
  { label: '深色', value: 'dark' },
  { label: '跟随系统', value: 'system' },
]

const resolvedThemeLabel = computed(() =>
  resolvedTheme.value === 'dark' ? '深色' : '浅色',
)
</script>

<template>
  <AppPage class="foundation-page">
    <header class="foundation-page__intro">
      <VanTag type="primary" round>仅开发环境</VanTag>
      <h1 class="foundation-page__title">移动端基础设施</h1>
      <p class="foundation-page__description">
        验证移动端设计变量、主题、Vant 基础能力、安全区与触控基线。
      </p>
    </header>

    <section
      class="foundation-section"
      aria-labelledby="foundation-token-title"
    >
      <h2 id="foundation-token-title" class="foundation-section__title">
        语义设计变量
      </h2>
      <div class="foundation-swatches" aria-label="状态颜色">
        <span class="foundation-swatch foundation-swatch--primary">主色</span>
        <span class="foundation-swatch foundation-swatch--success">成功</span>
        <span class="foundation-swatch foundation-swatch--warning">警告</span>
        <span class="foundation-swatch foundation-swatch--danger">危险</span>
      </div>
      <div class="foundation-surfaces" aria-label="Surface 层级">
        <span class="foundation-surface foundation-surface--primary"
          >Primary</span
        >
        <span class="foundation-surface foundation-surface--secondary"
          >Secondary</span
        >
        <span class="foundation-surface foundation-surface--raised"
          >Raised</span
        >
      </div>
      <div class="foundation-type-scale" aria-label="字体层级">
        <span class="foundation-type-scale__meta">Meta / 12</span>
        <span>Body / 14</span>
        <strong class="foundation-type-scale__label">Label / 16</strong>
        <strong class="foundation-type-scale__title">Title / 20</strong>
        <strong class="foundation-type-scale__display">26</strong>
      </div>
    </section>

    <section
      class="foundation-section"
      aria-labelledby="foundation-theme-title"
    >
      <h2 id="foundation-theme-title" class="foundation-section__title">
        主题
      </h2>
      <div class="foundation-actions">
        <VanButton
          v-for="option in themeOptions"
          :key="option.value"
          :type="mode === option.value ? 'primary' : 'default'"
          :aria-pressed="mode === option.value"
          @click="themeStore.setMode(option.value)"
        >
          {{ option.label }}
        </VanButton>
      </div>
      <VanCellGroup>
        <VanCell title="当前解析主题" :value="resolvedThemeLabel" />
      </VanCellGroup>
    </section>

    <section class="foundation-section" aria-labelledby="foundation-vant-title">
      <h2 id="foundation-vant-title" class="foundation-section__title">
        Vant 基础能力
      </h2>
      <VanCellGroup>
        <VanField
          v-model="fieldValue"
          name="foundation-input"
          label="输入框"
          placeholder="请输入验证内容"
          clearable
        />
        <VanCell title="标签">
          <template #value>
            <div class="foundation-tags">
              <VanTag type="success">正常</VanTag>
              <VanTag type="warning">注意</VanTag>
              <VanTag type="danger">异常</VanTag>
            </div>
          </template>
        </VanCell>
      </VanCellGroup>
      <div class="foundation-notices" aria-label="NoticeBar 状态映射">
        <VanNoticeBar class="mobile-notice-bar--success" text="成功提示" />
        <VanNoticeBar class="mobile-notice-bar--warning" text="警告提示" />
        <VanNoticeBar class="mobile-notice-bar--danger" text="错误提示" />
      </div>
      <VanButton
        block
        type="primary"
        data-testid="open-foundation-sheet"
        @click="sheetVisible = true"
      >
        打开底部面板
      </VanButton>
    </section>

    <section
      class="foundation-section foundation-safe-area"
      aria-labelledby="foundation-safe-area-title"
      data-testid="safe-area-status"
    >
      <h2 id="foundation-safe-area-title" class="foundation-section__title">
        安全区
      </h2>
      <p>应用框架与页面已接入顶部、左右及底部设备安全区。</p>
    </section>

    <VanPopup
      v-model:show="sheetVisible"
      position="bottom"
      round
      class="foundation-sheet"
    >
      <section aria-labelledby="foundation-sheet-title">
        <h2 id="foundation-sheet-title" class="foundation-section__title">
          底部面板
        </h2>
        <p class="foundation-sheet__description">
          弹出层使用全局语义设计变量，并为底部安全区留出空间。
        </p>
        <VanButton block type="primary" @click="sheetVisible = false">
          关闭
        </VanButton>
      </section>
    </VanPopup>
  </AppPage>
</template>

<style scoped>
.foundation-page__intro,
.foundation-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--bg-surface);
  border: var(--border-width) solid var(--border-subtle);
  border-radius: var(--radius-card);
}

.foundation-page__intro {
  align-items: flex-start;
  background: var(--bg-surface-raised);
  box-shadow: var(--shadow-card);
}

.foundation-page__title {
  color: var(--text-primary);
  font-size: var(--font-size-title);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-title);
}

.foundation-page__description,
.foundation-sheet__description,
.foundation-safe-area {
  color: var(--text-secondary);
}

.foundation-section__title {
  color: var(--text-primary);
  font-size: var(--font-size-label);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-label);
}

.foundation-swatches,
.foundation-surfaces,
.foundation-actions,
.foundation-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--layout-content-gap);
}

.foundation-notices {
  display: grid;
  gap: var(--layout-content-gap);
}

.foundation-swatch {
  min-width: var(--touch-target-min);
  padding: var(--layout-content-gap) var(--space-3);
  border: var(--border-width) solid var(--border-subtle);
  border-radius: var(--radius-round);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
  line-height: var(--line-height-caption);
  text-align: center;
}

.foundation-swatch--primary {
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.foundation-swatch--success {
  color: var(--status-success);
  background: var(--status-success-soft);
}

.foundation-swatch--warning {
  color: var(--status-warning);
  background: var(--status-warning-soft);
}

.foundation-swatch--danger {
  color: var(--status-danger);
  background: var(--status-danger-soft);
}

.foundation-surface {
  display: grid;
  min-height: var(--touch-target-min);
  flex: 1;
  padding: var(--layout-content-gap);
  place-items: center;
  color: var(--text-secondary);
  border: var(--border-width) solid var(--border-subtle);
  border-radius: var(--radius-control);
  font-size: var(--font-size-caption);
}

.foundation-surface--primary {
  background: var(--bg-surface);
}

.foundation-surface--secondary {
  background: var(--bg-subtle);
}

.foundation-surface--raised {
  background: var(--bg-surface-raised);
  box-shadow: var(--shadow-card);
}

.foundation-type-scale {
  display: grid;
  gap: var(--layout-compact-gap);
  color: var(--text-primary);
}

.foundation-type-scale__meta {
  color: var(--text-tertiary);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

.foundation-type-scale__label {
  font-size: var(--font-size-label);
  line-height: var(--line-height-label);
}

.foundation-type-scale__title {
  font-size: var(--font-size-title);
  line-height: var(--line-height-title);
}

.foundation-type-scale__display {
  font-size: var(--font-size-display);
  line-height: var(--line-height-display);
}

.foundation-actions > * {
  min-width: var(--touch-target-min);
}

.foundation-sheet {
  padding: var(--space-5) max(var(--space-4), var(--safe-area-right))
    calc(var(--space-5) + var(--safe-area-bottom))
    max(var(--space-4), var(--safe-area-left));
}

.foundation-sheet section {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
</style>
