<script setup lang="ts">
import { Badge as VanBadge, Icon as VanIcon } from 'vant'

withDefaults(
  defineProps<{
    notificationDot?: boolean
  }>(),
  {
    notificationDot: false,
  },
)

const emit = defineEmits<{
  notificationClick: []
}>()
</script>

<template>
  <div class="mobile-global-header" data-testid="mobile-global-header">
    <strong class="mobile-global-header__brand">思余AI中控台</strong>

    <button
      class="mobile-global-header__notification"
      type="button"
      aria-label="通知"
      @click="emit('notificationClick')"
    >
      <VanBadge :dot="notificationDot">
        <VanIcon name="bell" aria-hidden="true" />
      </VanBadge>
    </button>
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
  background: var(--bg-surface);
  border-bottom: var(--border-width) solid var(--border-subtle);
}

.mobile-global-header__brand {
  overflow: hidden;
  font-size: var(--font-size-label);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-label);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-global-header__notification {
  display: inline-flex;
  width: var(--touch-target-min);
  min-width: var(--touch-target-min);
  height: var(--touch-target-min);
  align-items: center;
  justify-content: center;
  padding: 0;
  color: var(--text-secondary);
  background: none;
  border: none;
  border-radius: var(--radius-round);
}

.mobile-global-header__notification:active {
  color: var(--text-primary);
  background: var(--bg-surface-hover);
}

.mobile-global-header__notification .van-icon {
  font-size: var(--font-size-title);
}
</style>
