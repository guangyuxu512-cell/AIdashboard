<script setup lang="ts">
import { Icon as VanIcon, NavBar as VanNavBar } from 'vant'

defineProps<{
  title: string
}>()

const emit = defineEmits<{
  back: []
}>()
</script>

<template>
  <div class="mobile-detail-header" data-testid="mobile-detail-header">
    <VanNavBar :title="title" :border="false">
      <template #left>
        <button
          class="mobile-detail-header__back"
          type="button"
          aria-label="返回"
          @click="emit('back')"
        >
          <VanIcon name="arrow-left" aria-hidden="true" />
        </button>
      </template>
    </VanNavBar>
  </div>
</template>

<style scoped>
.mobile-detail-header {
  padding-right: max(
    0px,
    calc(var(--safe-area-right) - var(--layout-page-padding-x))
  );
  padding-left: max(
    0px,
    calc(var(--safe-area-left) - var(--layout-page-padding-x))
  );
  background: var(--bg-surface-raised);
}

.mobile-detail-header__back {
  display: inline-grid;
  width: var(--touch-target-min);
  min-width: var(--touch-target-min);
  height: var(--touch-target-min);
  padding: 0;
  color: var(--color-primary);
  background: transparent;
  border: 0;
  border-radius: var(--radius-round);
  place-items: center;
}

.mobile-detail-header__back:active {
  color: var(--color-primary-active);
  background: var(--bg-surface-hover);
}

.mobile-detail-header__back .van-icon {
  font-size: var(--icon-size-small);
}
</style>
