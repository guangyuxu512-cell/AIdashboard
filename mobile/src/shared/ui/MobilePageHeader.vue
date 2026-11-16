<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string
    testId?: string
    titleTestId?: string
  }>(),
  {
    testId: 'mobile-page-header',
    titleTestId: 'mobile-page-title',
  },
)
</script>

<template>
  <div class="mobile-page-header" :data-testid="testId">
    <div class="mobile-page-header__leading">
      <slot name="left-action" />
    </div>

    <strong class="mobile-page-header__title" :data-testid="titleTestId">
      {{ title }}
    </strong>

    <div class="mobile-page-header__actions">
      <slot name="right-actions" />
    </div>
  </div>
</template>

<style scoped>
.mobile-page-header {
  display: grid;
  width: 100%;
  min-width: 0;
  height: var(--visual-v2-page-header-height);
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  gap: var(--visual-v2-page-header-gap);
  padding-right: max(var(--visual-v2-page-padding-x), var(--safe-area-right));
  padding-left: max(var(--visual-v2-page-padding-x), var(--safe-area-left));
  align-items: center;
  color: var(--visual-v2-page-text-primary);
  background: var(--visual-v2-page-header-background);
}

.mobile-page-header__leading,
.mobile-page-header__actions {
  display: flex;
  min-width: 0;
  align-items: center;
}

.mobile-page-header__leading {
  justify-content: flex-start;
}

.mobile-page-header__actions {
  gap: var(--visual-v2-page-header-actions-gap);
  justify-content: flex-end;
}

.mobile-page-header__title {
  overflow: hidden;
  font-size: var(--typography-v2-page-title-size);
  font-weight: var(--typography-v2-page-title-weight);
  line-height: var(--typography-v2-page-title-line-height);
  letter-spacing: var(--typography-v2-page-title-letter-spacing);
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
