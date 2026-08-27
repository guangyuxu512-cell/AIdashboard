<script setup lang="ts">
import { Icon as VanIcon } from 'vant'

defineProps<{
  title: string
}>()

const emit = defineEmits<{
  back: []
}>()
</script>

<template>
  <nav
    class="mobile-detail-header"
    data-testid="mobile-detail-header"
    aria-label="详情页导航"
  >
    <button
      class="mobile-detail-header__back mobile-icon-button mobile-pressable"
      type="button"
      aria-label="返回"
      @click="emit('back')"
    >
      <VanIcon
        class="mobile-detail-header__back-icon"
        name="arrow-left"
        aria-hidden="true"
      />
    </button>

    <div
      class="mobile-detail-header__title"
      data-testid="mobile-detail-header-title"
    >
      {{ title }}
    </div>

    <div
      class="mobile-detail-header__right"
      data-testid="mobile-detail-header-right"
    >
      <slot name="right" />
    </div>
  </nav>
</template>

<style scoped>
.mobile-detail-header {
  --mobile-detail-header-inline-inset: max(
    var(--layout-page-padding-x),
    var(--safe-area-left),
    var(--safe-area-right)
  );

  display: grid;
  width: 100%;
  height: var(--layout-detail-header-height);
  padding-inline: var(--mobile-detail-header-inline-inset);
  box-sizing: border-box;
  grid-template-columns:
    var(--touch-target-min) minmax(0, 1fr)
    var(--touch-target-min);
  align-items: center;
  background: var(--bg-surface-raised);
}

.mobile-detail-header__back {
  grid-column: 1;
  justify-self: start;
  color: var(--color-primary);
}

.mobile-detail-header__back-icon {
  font-size: var(--icon-size-default);
}

.mobile-detail-header__title {
  min-width: 0;
  grid-column: 2;
  overflow: hidden;
  color: var(--text-primary);
  font-size: var(--font-size-title);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-title);
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-detail-header__right {
  display: grid;
  width: var(--touch-target-min);
  height: var(--touch-target-min);
  grid-column: 3;
  justify-self: end;
  place-items: center;
}
</style>
