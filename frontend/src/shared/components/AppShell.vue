<script setup lang="ts">
import { computed } from 'vue'
import { NMenu } from 'naive-ui'
import type { MenuOption } from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'

export interface AppNavigationItem {
  key: string
  label: string
  to: string
}

const props = withDefaults(
  defineProps<{
    appName?: string
    contextLabel?: string
    navigation: AppNavigationItem[]
  }>(),
  {
    appName: '电商 AI 中控台',
    contextLabel: '桌面控制平台',
  },
)

const route = useRoute()
const router = useRouter()

const menuOptions = computed<MenuOption[]>(() =>
  props.navigation.map((item) => ({ key: item.key, label: item.label })),
)

const activeNavigationKey = computed(
  () => props.navigation.find((item) => item.to === route.path)?.key ?? null,
)

function navigate(key: string): void {
  const target = props.navigation.find((item) => item.key === key)
  if (target && target.to !== route.path) {
    void router.push(target.to)
  }
}
</script>

<template>
  <div class="app-shell">
    <aside class="app-shell__sidebar">
      <div class="app-shell__brand">
        <span class="app-shell__brand-mark" aria-hidden="true">AI</span>
        <div>
          <strong>{{ appName }}</strong>
          <span>{{ contextLabel }}</span>
        </div>
      </div>
      <nav class="app-shell__navigation" aria-label="主导航">
        <NMenu
          :value="activeNavigationKey"
          :options="menuOptions"
          inverted
          @update:value="navigate"
        />
      </nav>
      <div class="app-shell__sidebar-footer">阶段 0B · UI 基础设施</div>
    </aside>

    <section class="app-shell__workspace">
      <header class="app-shell__topbar">
        <div class="app-shell__topbar-leading">
          <slot name="topbar-leading">
            <span class="app-shell__environment">本地桌面环境</span>
          </slot>
        </div>
        <div class="app-shell__topbar-actions">
          <slot name="topbar-actions" />
        </div>
      </header>
      <main class="app-shell__content">
        <slot />
      </main>
    </section>
  </div>
</template>

<style scoped>
.app-shell {
  display: grid;
  width: 100%;
  height: 100%;
  grid-template-columns: var(--layout-sidebar-width) minmax(0, 1fr);
  overflow: hidden;
  background: var(--color-bg-page);
}

.app-shell__sidebar {
  display: flex;
  min-height: 0;
  flex-direction: column;
  color: var(--color-text-inverse);
  background: var(--color-bg-sidebar);
}

.app-shell__brand {
  display: flex;
  height: var(--layout-topbar-height);
  flex: 0 0 var(--layout-topbar-height);
  align-items: center;
  gap: var(--space-3);
  padding: 0 var(--space-4);
  border-bottom: 1px solid rgb(255 255 255 / 8%);
}

.app-shell__brand-mark {
  display: grid;
  width: var(--control-height-default);
  height: var(--control-height-default);
  flex: 0 0 var(--control-height-default);
  place-items: center;
  border-radius: var(--radius-control);
  color: var(--color-text-inverse);
  background: var(--color-primary);
  font-size: var(--font-size-secondary);
  font-weight: var(--font-weight-semibold);
}

.app-shell__brand strong,
.app-shell__brand span {
  display: block;
}

.app-shell__brand strong {
  font-size: var(--font-size-body);
  line-height: var(--line-height-compact);
}

.app-shell__brand div > span {
  margin-top: var(--space-1);
  color: rgb(255 255 255 / 56%);
  font-size: var(--font-size-secondary);
}

.app-shell__navigation {
  min-height: 0;
  flex: 1;
  padding: var(--space-3) var(--space-2);
  overflow-y: auto;
}

.app-shell__sidebar-footer {
  padding: var(--space-4);
  color: rgb(255 255 255 / 48%);
  font-size: var(--font-size-secondary);
}

.app-shell__workspace {
  display: grid;
  min-width: 0;
  min-height: 0;
  grid-template-rows: var(--layout-topbar-height) minmax(0, 1fr);
}

.app-shell__topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--layout-page-padding-x);
  border-bottom: 1px solid var(--color-border-default);
  background: var(--color-bg-card);
}

.app-shell__topbar-leading,
.app-shell__topbar-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.app-shell__environment {
  color: var(--color-text-secondary);
  font-size: var(--font-size-secondary);
}

.app-shell__content {
  min-width: 0;
  min-height: 0;
  overflow: auto;
}
</style>
