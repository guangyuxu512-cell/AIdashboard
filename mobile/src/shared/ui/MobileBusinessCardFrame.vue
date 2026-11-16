<script setup lang="ts">
import { MobileIcon } from '@/shared/icons'

defineProps<{
  label: string
  buttonTestId?: string
  chevronTestId?: string
}>()

const emit = defineEmits<{
  activate: []
}>()
</script>

<template>
  <article
    class="mobile-business-card-frame mobile-business-card-surface-v2 mobile-press-surface"
  >
    <button
      type="button"
      class="mobile-business-card-frame__main"
      :aria-label="label"
      :data-testid="buttonTestId"
      @click="emit('activate')"
    />

    <span
      class="mobile-business-card-frame__leading"
      data-testid="business-card-leading"
      aria-hidden="true"
    >
      <slot name="leading" />
    </span>

    <span class="mobile-business-card-frame__content">
      <strong class="mobile-business-card-frame__title">
        <slot name="title" />
      </strong>
      <span class="mobile-business-card-frame__status">
        <slot name="status" />
      </span>
      <span class="mobile-business-card-frame__meta">
        <slot name="meta" />
      </span>
    </span>

    <MobileIcon
      class="mobile-business-card-frame__chevron"
      name="chevron-right"
      :data-testid="chevronTestId || 'business-card-chevron'"
    />
  </article>
</template>

<style scoped>
.mobile-business-card-frame {
  position: relative;
  display: grid;
  width: 100%;
  min-width: 0;
  min-height: var(--visual-v2-business-card-min-height);
  padding: var(--visual-v2-business-card-padding-top)
    var(--visual-v2-business-card-padding-right)
    var(--visual-v2-business-card-padding-bottom)
    var(--visual-v2-business-card-padding-left);
  overflow: hidden;
  color: var(--visual-v2-page-text-primary);
  text-align: left;
  border: var(--visual-v2-business-card-border-width) solid
    var(--visual-v2-business-card-border-color);
  border-radius: var(--visual-v2-business-card-radius);
  grid-template-columns:
    var(--visual-v2-business-card-leading-column) minmax(0, 1fr)
    var(--visual-v2-business-card-trailing-column);
  align-items: center;
}

.mobile-business-card-frame__main {
  position: absolute;
  z-index: 2;
  inset: 0;
  padding: 0;
  background: transparent;
  border: 0;
  border-radius: var(--visual-v2-business-card-radius);
  cursor: pointer;
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
}

.mobile-business-card-frame__main:focus-visible {
  outline: var(--focus-ring-width) solid var(--focus-ring-color);
  outline-offset: calc(var(--focus-ring-offset) * -1);
}

.mobile-business-card-frame:has(.mobile-business-card-frame__main:active) {
  background: var(--visual-v2-business-card-pressed-background);
  border-color: var(--visual-v2-business-card-pressed-border-color);
  box-shadow: var(--visual-v2-business-card-pressed-shadow);
  transform: scale(var(--press-scale-card));
}

.mobile-business-card-frame__leading {
  position: relative;
  z-index: 1;
  display: flex;
  height: var(--visual-v2-business-card-leading-height);
  align-items: center;
  justify-content: center;
}

.mobile-business-card-frame__content {
  position: relative;
  z-index: 1;
  display: block;
  min-width: 0;
}

.mobile-business-card-frame__title,
.mobile-business-card-frame__status,
.mobile-business-card-frame__meta {
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
}

.mobile-business-card-frame__title {
  display: block;
  margin: 0 0 var(--visual-v2-business-card-title-gap);
  font-size: var(--typography-v2-business-card-title-size);
  font-weight: var(--typography-v2-business-card-title-weight);
  line-height: var(--typography-v2-business-card-title-line-height);
  letter-spacing: var(--typography-v2-business-card-title-letter-spacing);
  text-overflow: ellipsis;
}

.mobile-business-card-frame__status,
.mobile-business-card-frame__meta {
  display: flex;
  gap: var(--visual-v2-business-card-inline-gap);
  align-items: center;
  text-overflow: ellipsis;
}

.mobile-business-card-frame__status {
  margin-bottom: var(--visual-v2-business-card-status-gap);
  font-size: var(--typography-v2-status-size);
  font-weight: var(--typography-v2-status-weight);
  line-height: var(--typography-v2-status-line-height);
}

.mobile-business-card-frame__meta {
  color: var(--visual-v2-business-card-meta-color);
  font-size: var(--typography-v2-meta-size);
  font-weight: var(--typography-v2-meta-weight);
  line-height: var(--typography-v2-meta-line-height);
}

.mobile-business-card-frame__chevron {
  position: relative;
  z-index: 1;
  width: var(--visual-v2-business-card-chevron-size);
  height: var(--visual-v2-business-card-chevron-size);
  color: var(--visual-v2-business-card-chevron-color);
  font-size: var(--visual-v2-business-card-chevron-size);
  justify-self: end;
}
</style>
