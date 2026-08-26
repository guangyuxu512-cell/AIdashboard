<script setup lang="ts">
import { Badge as VanBadge, Icon as VanIcon } from 'vant'
import { computed } from 'vue'

const emit = defineEmits<{
  themeToggle: []
  notificationClick: []
}>()

const props = withDefaults(
  defineProps<{
    notificationDot?: boolean
    resolvedTheme?: 'light' | 'dark'
  }>(),
  {
    notificationDot: false,
    resolvedTheme: 'light',
  },
)

const themeActionLabel = computed(() =>
  props.resolvedTheme === 'dark' ? '切换到浅色主题' : '切换到深色主题',
)
const themeActionIcon = computed(() =>
  props.resolvedTheme === 'dark' ? 'closed-eye' : 'bulb-o',
)
</script>

<template>
  <div class="mobile-global-header" data-testid="mobile-global-header">
    <strong class="mobile-global-header__brand">思余AI中控台</strong>

    <div class="mobile-global-header__actions">
      <button
        class="mobile-icon-button mobile-pressable"
        type="button"
        :aria-label="themeActionLabel"
        data-testid="theme-toggle"
        @click="emit('themeToggle')"
      >
        <VanIcon :name="themeActionIcon" aria-hidden="true" />
      </button>
      <button
        class="mobile-icon-button mobile-pressable"
        type="button"
        aria-label="通知"
        @click="emit('notificationClick')"
      >
        <VanBadge :dot="notificationDot">
          <VanIcon name="bell" aria-hidden="true" />
        </VanBadge>
      </button>
    </div>
  </div>
</template>

<style scoped>
.mobile-global-header {
  display: flex;
  min-width: 0;
  min-height: var(--layout-header-height);
  align-items: center;
  justify-content: space-between;
  padding-right: max(var(--layout-page-padding-x), var(--safe-area-right));
  padding-left: max(var(--layout-page-padding-x), var(--safe-area-left));
  color: var(--text-primary);
  background: var(--bg-surface-raised);
}

.mobile-global-header__brand {
  overflow: hidden;
  font-size: var(--font-size-label);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-label);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-global-header__actions {
  display: flex;
  flex: none;
  gap: var(--space-1);
  align-items: center;
}
</style>
