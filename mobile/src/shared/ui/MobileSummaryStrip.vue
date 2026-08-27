<script setup lang="ts">
import { Icon as VanIcon } from 'vant'
import type { PropType } from 'vue'

type MobileSummaryTone = 'primary' | 'success' | 'muted' | 'neutral'

interface MobileSummaryItem {
  key: string
  label: string
  value: string | number
  icon: string
  tone?: MobileSummaryTone
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
</script>

<template>
  <section class="mobile-summary-strip" :aria-label="ariaLabel">
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
        <VanIcon
          class="mobile-summary-strip__icon"
          :name="item.icon"
          aria-hidden="true"
        />
        <strong
          class="mobile-summary-strip__value"
          :data-testid="`summary-${item.key}`"
        >
          {{ item.value }}
        </strong>
        <span class="mobile-summary-strip__label">{{ item.label }}</span>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.mobile-summary-strip {
  width: 100%;
  min-width: 0;
  height: var(--layout-summary-height);
  flex: none;
  padding: var(--space-2)
    max(var(--layout-page-padding-x), var(--safe-area-right)) 0
    max(var(--layout-page-padding-x), var(--safe-area-left));
}

.mobile-summary-strip__surface {
  display: grid;
  height: calc(100% - var(--space-2));
  min-width: 0;
  margin: 0;
  padding: 0;
  grid-auto-columns: minmax(0, 1fr);
  grid-auto-flow: column;
  list-style: none;
  overflow: hidden;
}

.mobile-summary-strip__item {
  position: relative;
  display: grid;
  min-width: 0;
  grid-template-rows: auto auto auto;
  row-gap: var(--space-1);
  padding-inline: var(--space-2);
  align-content: center;
  justify-items: center;
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

.mobile-summary-strip__icon,
.mobile-summary-strip__value,
.mobile-summary-strip__label {
  min-width: 0;
  margin: 0;
}

.mobile-summary-strip__icon {
  display: grid;
  width: var(--icon-size-default);
  height: var(--icon-size-default);
  color: var(--text-secondary);
  font-size: var(--icon-size-default);
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
