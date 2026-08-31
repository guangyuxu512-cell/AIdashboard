<script setup lang="ts">
import { MobileIcon } from '@/shared/icons'
import type { MobileDetailHeaderAction } from './mobile-detail-header-action'

withDefaults(
  defineProps<{
    title: string
    visualV2?: boolean
    rightAction?: MobileDetailHeaderAction | null
  }>(),
  { rightAction: null, visualV2: false },
)

const emit = defineEmits<{
  back: []
  right: []
}>()
</script>

<template>
  <nav
    class="mobile-detail-header"
    :class="{ 'mobile-detail-header--visual-v2': visualV2 }"
    data-testid="mobile-detail-header"
    aria-label="详情页导航"
  >
    <button
      class="mobile-detail-header__back mobile-icon-button mobile-pressable"
      type="button"
      aria-label="返回"
      @click="emit('back')"
    >
      <MobileIcon class="mobile-detail-header__back-icon" name="back" />
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
      <button
        v-if="rightAction"
        class="mobile-detail-header__action mobile-icon-button mobile-pressable"
        type="button"
        :aria-label="rightAction.label"
        @click="emit('right')"
      >
        <MobileIcon
          class="mobile-detail-header__action-icon"
          :name="rightAction.icon"
        />
      </button>
      <slot v-else name="right" />
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

.mobile-detail-header__action-icon {
  font-size: var(--icon-size-default);
}

.mobile-detail-header--visual-v2 {
  --mobile-detail-header-inline-inset: max(
    var(--visual-v2-detail-header-padding-x),
    var(--safe-area-left),
    var(--safe-area-right)
  );

  height: var(--visual-v2-detail-header-height);
  grid-template-columns:
    var(--visual-v2-detail-header-action-slot) minmax(0, 1fr)
    var(--visual-v2-detail-header-action-slot);
  background: transparent;
}

.mobile-detail-header--visual-v2 .mobile-detail-header__back,
.mobile-detail-header--visual-v2 .mobile-detail-header__right {
  width: var(--visual-v2-detail-header-action-slot);
  height: var(--visual-v2-detail-header-action-slot);
}

.mobile-detail-header--visual-v2 .mobile-detail-header__back-icon,
.mobile-detail-header--visual-v2 .mobile-detail-header__action-icon {
  font-size: var(--visual-v2-detail-header-icon-size);
}

.mobile-detail-header--visual-v2 .mobile-detail-header__title {
  color: var(--visual-v2-page-text-primary);
  font-size: var(--typography-v2-detail-title-size);
  font-weight: var(--typography-v2-detail-title-weight);
  line-height: var(--typography-v2-detail-title-line-height);
}

.mobile-detail-header--visual-v2 .mobile-detail-header__back,
.mobile-detail-header--visual-v2 .mobile-detail-header__action {
  color: var(--visual-v2-page-text-primary);
}

.mobile-detail-header--visual-v2 .mobile-detail-header__back::before,
.mobile-detail-header--visual-v2 .mobile-detail-header__action::before {
  background: transparent;
  border-color: transparent;
  box-shadow: none;
}

.mobile-detail-header--visual-v2 .mobile-detail-header__back:active::before,
.mobile-detail-header--visual-v2 .mobile-detail-header__action:active::before {
  background: var(--visual-v2-detail-weak-background);
}
</style>
