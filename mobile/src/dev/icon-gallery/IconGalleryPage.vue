<script setup lang="ts">
import { computed } from 'vue'

import { useThemeStore } from '@/app/stores/theme'
import {
  MOBILE_ICON_GALLERY_GROUPS,
  MOBILE_ICON_REGISTRY,
  MobileIcon,
} from '@/shared/icons'

const themeStore = useThemeStore()
const primaryIconNames = new Set(['device', 'task'])

const groups = computed(() =>
  MOBILE_ICON_GALLERY_GROUPS.map((group) => ({
    ...group,
    icons: group.names.map((name) => ({
      name,
      definition: MOBILE_ICON_REGISTRY[name],
    })),
  })),
)

function roleLabel(role: string): string {
  const labels: Record<string, string> = {
    primary: '主业务',
    runtime: '运行摘要',
    capability: '能力',
    status: '状态',
    navigation: '导航',
    action: '操作',
  }
  return labels[role] ?? role
}
</script>

<template>
  <main class="icon-gallery" aria-label="移动端图标总览">
    <header class="icon-gallery__header">
      <div>
        <h1>图标总览</h1>
        <p>开发预览</p>
      </div>
      <button
        class="mobile-icon-button mobile-pressable"
        type="button"
        aria-label="切换主题"
        @click="themeStore.toggleResolvedTheme"
      >
        <MobileIcon name="theme-toggle" />
      </button>
    </header>

    <section
      v-for="group in groups"
      :key="group.label"
      class="icon-gallery__group"
    >
      <h2>{{ group.label }}</h2>
      <ul class="icon-gallery__grid">
        <li
          v-for="icon in group.icons"
          :key="icon.name"
          class="icon-gallery__item"
        >
          <MobileIcon
            class="icon-gallery__icon"
            :name="icon.name"
            :tile="primaryIconNames.has(icon.name)"
          />
          <div class="icon-gallery__copy">
            <strong>{{ icon.definition.label }}</strong>
            <code>{{ icon.name }}</code>
            <span>{{ roleLabel(icon.definition.role) }}</span>
          </div>
        </li>
      </ul>
    </section>
  </main>
</template>

<style scoped>
.icon-gallery {
  min-height: 100dvh;
  padding: max(var(--layout-page-padding-y), var(--safe-area-top))
    max(var(--layout-page-padding-x), var(--safe-area-right))
    max(var(--layout-page-padding-y), var(--safe-area-bottom))
    max(var(--layout-page-padding-x), var(--safe-area-left));
  color: var(--text-primary);
  background: var(--bg-app);
}

.icon-gallery__header {
  display: flex;
  gap: var(--layout-content-gap);
  align-items: center;
  justify-content: space-between;
}

.icon-gallery__header h1,
.icon-gallery__group h2,
.icon-gallery__copy strong,
.icon-gallery__copy code,
.icon-gallery__copy span {
  display: block;
}

.icon-gallery__header h1 {
  font-size: var(--font-size-title);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-title);
}

.icon-gallery__header p,
.icon-gallery__copy span {
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

.icon-gallery__group {
  margin-top: var(--layout-section-gap);
}

.icon-gallery__group h2 {
  font-size: var(--font-size-label);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-label);
}

.icon-gallery__grid {
  display: grid;
  margin: var(--layout-content-gap) 0 0;
  padding: 0;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--layout-card-gap);
  list-style: none;
}

.icon-gallery__item {
  display: flex;
  min-width: 0;
  min-height: var(--touch-target-min);
  gap: var(--layout-content-gap);
  padding: var(--space-3);
  align-items: center;
  background: var(--bg-surface);
  border: var(--border-width) solid transparent;
  border-radius: var(--radius-panel);
  box-shadow: var(--appearance-border-surface);
}

.icon-gallery__icon {
  width: var(--icon-size-default);
  height: var(--icon-size-default);
  color: var(--text-secondary);
  font-size: var(--icon-size-default);
}

.icon-gallery__icon.mobile-icon--tile {
  width: var(--icon-size-card-leading);
  height: var(--icon-size-card-leading);
}

.icon-gallery__copy {
  min-width: 0;
}

.icon-gallery__copy strong {
  overflow: hidden;
  font-size: var(--font-size-action);
  font-weight: var(--font-weight-medium);
  line-height: var(--line-height-action);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.icon-gallery__copy code {
  overflow: hidden;
  color: var(--text-muted);
  font-family: var(--font-family-mono);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
