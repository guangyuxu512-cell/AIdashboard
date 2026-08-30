<script setup lang="ts">
import { Badge as VanBadge } from 'vant'
import { computed } from 'vue'

import { MobileIcon, type MobileIconName } from '@/shared/icons'

const emit = defineEmits<{
  themeToggle: []
  notificationClick: []
}>()

const props = withDefaults(
  defineProps<{
    notificationDot?: boolean
    resolvedTheme?: 'light' | 'dark'
    pageTitle?: string
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
  <div
    class="mobile-global-header"
    :class="{ 'mobile-global-header--page': pageTitle }"
    data-testid="mobile-global-header"
  >
    <span v-if="pageTitle" class="mobile-global-header__leading" />
    <strong
      v-if="pageTitle"
      class="mobile-global-header__page-title"
      data-testid="mobile-global-page-title"
    >
      {{ pageTitle }}
    </strong>
    <strong v-else class="mobile-global-header__brand">思余AI中控台</strong>

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
.mobile-global-header {
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

.mobile-global-header--page {
  height: var(--device-list-header-height);
  padding-right: max(var(--device-list-page-padding-x), var(--safe-area-right));
  padding-left: max(var(--device-list-page-padding-x), var(--safe-area-left));
  background: var(--device-list-header-background);
  color: var(--device-list-text-primary);
  font-family: var(--device-list-font-family);
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  display: grid;
}

.mobile-global-header__leading {
  min-width: 0;
}

.mobile-global-header__page-title {
  overflow: hidden;
  font-size: var(--device-list-title-size);
  font-weight: var(--device-list-title-weight);
  line-height: var(--device-list-title-line-height);
  letter-spacing: var(--device-list-title-letter-spacing);
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-global-header--page .mobile-global-header__actions {
  justify-self: end;
}

.mobile-global-header--page :deep(.mobile-icon-button) {
  --control-size-icon-button: var(--device-list-header-control-size);
}

.mobile-global-header__actions {
  display: flex;
  flex: none;
  gap: var(--layout-compact-gap);
  align-items: center;
}

.mobile-header-icon {
  display: block;
  width: var(--icon-size-default);
  height: var(--icon-size-default);
  object-fit: contain;
}
</style>
