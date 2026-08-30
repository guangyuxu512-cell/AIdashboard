<script setup lang="ts">
import type { PropType } from 'vue'

import { MobileIcon, type MobileIconName } from '@/shared/icons'

type MobileSummaryTone = 'primary' | 'success' | 'muted' | 'neutral'

interface MobileSummaryItem {
  key: string
  label: string
  value: string | number
  icon?: MobileIconName
  tone?: MobileSummaryTone
  interactive?: boolean
  selected?: boolean
  disabled?: boolean
  ariaLabel?: string
}

defineProps({
  items: {
    type: Array as PropType<readonly MobileSummaryItem[]>,
    required: true,
    validator: (items: readonly MobileSummaryItem[]) =>
      items.length >= 2 && items.length <= 4,
  },
  ariaLabel: {
    type: String,
    default: '数据总览',
  },
  busy: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits<{
  select: [key: string]
}>()
</script>

<template>
  <section
    class="mobile-summary-strip"
    :class="{
      'mobile-summary-strip--without-icons': items.every((item) => !item.icon),
    }"
    :aria-label="ariaLabel"
  >
    <ul
      class="mobile-summary-strip__surface mobile-section-surface"
      aria-live="polite"
      :aria-busy="busy"
    >
      <li
        v-for="item in items"
        :key="item.key"
        class="mobile-summary-strip__item"
        :class="`mobile-summary-strip__item--${item.tone ?? 'neutral'}`"
      >
        <component
          :is="item.interactive ? 'button' : 'div'"
          class="mobile-summary-strip__metric"
          :class="{
            'mobile-summary-strip__metric--interactive': item.interactive,
          }"
          :type="item.interactive ? 'button' : undefined"
          :disabled="item.interactive ? item.disabled : undefined"
          :aria-label="item.interactive ? item.ariaLabel : undefined"
          :aria-pressed="
            item.interactive && item.selected !== undefined
              ? item.selected
              : undefined
          "
          :data-testid="`summary-metric-${item.key}`"
          @click="
            item.interactive && !item.disabled ? emit('select', item.key) : null
          "
        >
          <MobileIcon
            v-if="item.icon"
            class="mobile-summary-strip__icon"
            :name="item.icon"
          />
          <strong
            class="mobile-summary-strip__value"
            :data-testid="`summary-${item.key}`"
          >
            {{ item.value }}
          </strong>
          <span class="mobile-summary-strip__label">{{ item.label }}</span>
        </component>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.mobile-summary-strip {
  width: 100%;
  min-width: 0;
  height: var(--summary-strip-height, var(--layout-summary-height));
  flex: none;
  padding: var(--summary-strip-padding-y, var(--layout-summary-padding-y))
    max(
      var(--summary-strip-padding-x, var(--layout-page-padding-x)),
      var(--summary-strip-safe-area-right, var(--safe-area-right))
    )
    var(--summary-strip-padding-y, var(--layout-summary-padding-y))
    max(
      var(--summary-strip-padding-x, var(--layout-page-padding-x)),
      var(--summary-strip-safe-area-left, var(--safe-area-left))
    );
}

.mobile-summary-strip__surface {
  display: grid;
  height: 100%;
  min-width: 0;
  margin: 0;
  padding: 0;
  grid-auto-columns: minmax(0, 1fr);
  grid-auto-flow: column;
  list-style: none;
  overflow: hidden;
  background: var(--summary-strip-background, var(--bg-surface));
  border-color: var(--summary-strip-border-color, transparent);
  border-radius: var(--summary-strip-radius, var(--radius-panel));
  box-shadow: var(--summary-strip-shadow, var(--shadow-card));
}

.mobile-summary-strip__item {
  position: relative;
  min-width: 0;
}

.mobile-summary-strip__metric {
  display: grid;
  width: 100%;
  height: 100%;
  grid-template-rows: auto auto auto;
  row-gap: var(--layout-summary-metric-gap);
  padding-inline: var(--layout-summary-metric-padding-x);
  align-content: center;
  justify-items: center;
}

.mobile-summary-strip__metric--interactive {
  min-height: var(--touch-target-min);
  appearance: none;
  color: inherit;
  font: inherit;
  background: transparent;
  border: 0;
}

.mobile-summary-strip__metric--interactive:disabled {
  opacity: 1;
}

.mobile-summary-strip--without-icons .mobile-summary-strip__metric {
  grid-template-rows: auto auto;
  row-gap: var(--summary-strip-metric-gap, var(--layout-summary-metric-gap));
  padding: var(--summary-strip-metric-padding-top, 0)
    var(
      --summary-strip-metric-padding-x,
      var(--layout-summary-metric-padding-x)
    )
    var(--summary-strip-metric-padding-bottom, 0);
}

.mobile-summary-strip__item + .mobile-summary-strip__item::before {
  position: absolute;
  top: var(--space-4);
  bottom: var(--space-4);
  left: 0;
  width: var(--border-width);
  background: var(--border-subtle);
  content: '';
}

.mobile-summary-strip--without-icons
  .mobile-summary-strip__item
  + .mobile-summary-strip__item::before {
  top: var(--summary-strip-divider-inset, var(--space-4));
  bottom: var(--summary-strip-divider-inset, var(--space-4));
  background: var(--summary-strip-divider, var(--border-subtle));
}

.mobile-summary-strip--without-icons
  .mobile-summary-strip__metric--interactive[aria-pressed='true']::after {
  position: absolute;
  bottom: var(--summary-strip-selected-bottom, var(--space-2));
  left: 50%;
  width: var(--summary-strip-selected-width, var(--space-6));
  height: var(--summary-strip-selected-height, var(--border-width));
  background: var(--summary-strip-selected-color, var(--text-primary));
  border-radius: var(--radius-round);
  content: '';
  transform: translateX(-50%);
}

.mobile-summary-strip__icon,
.mobile-summary-strip__value,
.mobile-summary-strip__label {
  min-width: 0;
  margin: 0;
}

.mobile-summary-strip--without-icons .mobile-summary-strip__label {
  color: var(--summary-strip-label-color, var(--text-secondary));
  font-size: var(--summary-strip-label-size, var(--font-size-caption));
  font-weight: var(--summary-strip-label-weight, var(--font-weight-medium));
  line-height: var(
    --summary-strip-label-line-height,
    var(--line-height-caption)
  );
}

.mobile-summary-strip__icon {
  display: grid;
  width: var(--icon-size-summary-metric);
  height: var(--icon-size-summary-metric);
  color: var(--text-secondary);
  font-size: var(--icon-size-summary-metric);
  place-items: center;
}

.mobile-summary-strip__label {
  overflow: hidden;
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
  line-height: var(--line-height-caption);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-summary-strip__value {
  overflow: hidden;
  color: var(--text-primary);
  font-size: var(--font-size-display);
  font-weight: var(--font-weight-bold);
  line-height: var(--line-height-display);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-summary-strip--without-icons .mobile-summary-strip__value {
  color: var(--summary-strip-value-color, var(--text-primary));
  font-size: var(--summary-strip-value-size, var(--font-size-display));
  font-weight: var(--summary-strip-value-weight, var(--font-weight-semibold));
  line-height: var(
    --summary-strip-value-line-height,
    var(--line-height-display)
  );
  letter-spacing: var(--summary-strip-value-letter-spacing, normal);
  font-variant-numeric: tabular-nums;
}

.mobile-summary-strip--without-icons
  .mobile-summary-strip__metric--interactive[aria-pressed='true']
  .mobile-summary-strip__value {
  color: var(--summary-strip-selected-value-color, var(--text-primary));
  font-weight: var(
    --summary-strip-selected-value-weight,
    var(--font-weight-semibold)
  );
}

.mobile-summary-strip--without-icons
  .mobile-summary-strip__metric--interactive[aria-pressed='true']
  .mobile-summary-strip__label {
  color: var(--summary-strip-selected-label-color, var(--text-secondary));
  font-weight: var(
    --summary-strip-selected-label-weight,
    var(--font-weight-semibold)
  );
}

.mobile-summary-strip__item--primary .mobile-summary-strip__value {
  color: var(--color-primary);
}

.mobile-summary-strip__item--success .mobile-summary-strip__value {
  color: var(--status-success);
}

.mobile-summary-strip__item--muted .mobile-summary-strip__value {
  color: var(--text-secondary);
}
</style>
