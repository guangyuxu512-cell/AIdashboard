<script setup lang="ts">
import { storeToRefs } from 'pinia'
import {
  Button as VanButton,
  Cell as VanCell,
  CellGroup as VanCellGroup,
  Field as VanField,
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
      <VanCellGroup inset>
        <VanCell title="当前解析主题" :value="resolvedThemeLabel" />
      </VanCellGroup>
    </section>

    <section class="foundation-section" aria-labelledby="foundation-vant-title">
      <h2 id="foundation-vant-title" class="foundation-section__title">
        Vant 基础能力
      </h2>
      <VanCellGroup inset>
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
      safe-area-inset-bottom
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
  box-shadow: var(--shadow-surface);
}

.foundation-page__intro {
  align-items: flex-start;
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
.foundation-actions,
.foundation-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.foundation-swatch {
  min-width: var(--touch-target-min);
  padding: var(--space-2) var(--space-3);
  color: var(--text-inverse);
  border-radius: var(--radius-round);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
  text-align: center;
}

.foundation-swatch--primary {
  background: var(--color-primary);
}

.foundation-swatch--success {
  background: var(--status-success);
}

.foundation-swatch--warning {
  background: var(--status-warning);
}

.foundation-swatch--danger {
  background: var(--status-danger);
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
