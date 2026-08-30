<script setup lang="ts">
import { Badge as VanBadge } from 'vant'
import { computed } from 'vue'

import { MobileIcon, type MobileIconName } from '@/shared/icons'
import MobilePageHeader from './MobilePageHeader.vue'

const emit = defineEmits<{
  themeToggle: []
  notificationClick: []
  settingsClick: []
}>()

const props = withDefaults(
  defineProps<{
    notificationDot?: boolean
    resolvedTheme?: 'light' | 'dark'
    pageTitle?: string
    menuEnabled?: boolean
  }>(),
  {
    notificationDot: false,
    resolvedTheme: 'light',
  },
)

const themeActionLabel = computed(() =>
  props.resolvedTheme === 'dark' ? '切换到浅色主题' : '切换到深色主题',
)

const themeIconName = computed<MobileIconName>(() =>
  props.resolvedTheme === 'dark' ? 'theme-light' : 'theme-dark',
)
</script>

<template>
  <MobilePageHeader
    v-if="pageTitle"
    class="mobile-global-header mobile-global-header--page"
    :title="pageTitle"
    test-id="mobile-global-header"
    title-test-id="mobile-global-page-title"
  >
    <template #left-action>
      <button
        v-if="menuEnabled"
        class="mobile-page-header__menu mobile-pressable"
        type="button"
        aria-label="打开主题设置"
        data-testid="mobile-header-menu"
        @click="emit('settingsClick')"
      >
        <MobileIcon name="menu" />
      </button>
    </template>

    <template #right-actions>
      <button
        class="mobile-page-header__action mobile-icon-button mobile-pressable"
        type="button"
        :aria-label="themeActionLabel"
        data-testid="theme-toggle"
        @click="emit('themeToggle')"
      >
        <MobileIcon class="mobile-header-icon" :name="themeIconName" />
      </button>
      <button
        class="mobile-page-header__action mobile-icon-button mobile-pressable"
        type="button"
        aria-label="通知"
        @click="emit('notificationClick')"
      >
        <VanBadge :dot="notificationDot">
          <MobileIcon class="mobile-header-icon" name="notification-bell" />
        </VanBadge>
      </button>
    </template>
  </MobilePageHeader>

  <div v-else class="mobile-global-header" data-testid="mobile-global-header">
    <strong class="mobile-global-header__brand">思余AI中控台</strong>

    <div class="mobile-global-header__actions">
      <button
        class="mobile-icon-button mobile-pressable"
        type="button"
        :aria-label="themeActionLabel"
        data-testid="theme-toggle"
        @click="emit('themeToggle')"
      >
        <MobileIcon class="mobile-header-icon" :name="themeIconName" />
      </button>
      <button
        class="mobile-icon-button mobile-pressable"
        type="button"
        aria-label="通知"
        @click="emit('notificationClick')"
      >
        <VanBadge :dot="notificationDot">
          <MobileIcon class="mobile-header-icon" name="notification-bell" />
        </VanBadge>
      </button>
    </div>
  </div>
</template>

<style scoped>
.mobile-global-header:not(.mobile-global-header--page) {
  display: flex;
  min-width: 0;
  height: var(--layout-header-height);
  align-items: center;
  justify-content: space-between;
  padding-right: max(var(--layout-page-padding-x), var(--safe-area-right));
  padding-left: max(var(--layout-page-padding-x), var(--safe-area-left));
  color: var(--text-primary);
  background: var(--bg-surface-raised);
}

.mobile-global-header__brand {
  overflow: hidden;
  font-size: var(--font-size-title);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-title);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-global-header__actions {
  display: flex;
  flex: none;
  gap: var(--layout-compact-gap);
  align-items: center;
}

.mobile-page-header__menu {
  display: grid;
  width: var(--touch-target-min);
  min-width: var(--touch-target-min);
  height: var(--touch-target-min);
  padding: 0;
  color: var(--visual-v2-page-text-primary);
  appearance: none;
  background: transparent;
  border: 0;
  border-radius: var(--radius-control);
  place-items: center;
}

.mobile-page-header__menu .mobile-icon {
  width: var(--visual-v2-page-menu-icon-width);
  height: var(--visual-v2-page-menu-icon-height);
  font-size: var(--visual-v2-page-menu-icon-width);
}

.mobile-page-header__action {
  --control-size-icon-button: var(--visual-v2-page-header-control-size);
}

:deep(.mobile-page-header .mobile-header-icon) {
  width: var(--visual-v2-page-action-icon-size);
  height: var(--visual-v2-page-action-icon-size);
  font-size: var(--visual-v2-page-action-icon-size);
}

.mobile-header-icon {
  display: block;
  width: var(--icon-size-default);
  height: var(--icon-size-default);
  object-fit: contain;
}
</style>
