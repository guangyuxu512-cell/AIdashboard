<script setup lang="ts">
import type { PropType } from 'vue'

type MobileSummaryTone = 'primary' | 'success' | 'muted' | 'neutral'

interface MobileSummaryItem {
  key: string
  label: string
  value: string | number
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
    <dl
      class="mobile-summary-strip__surface mobile-section-surface"
      aria-live="polite"
      :aria-busy="busy"
    >
      <div
        v-for="item in items"
        :key="item.key"
        class="mobile-summary-strip__item"
        :class="`mobile-summary-strip__item--${item.tone ?? 'neutral'}`"
      >
        <dd :data-testid="`summary-${item.key}`">{{ item.value }}</dd>
        <dt>{{ item.label }}</dt>
      </div>
    </dl>
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
  grid-auto-columns: minmax(0, 1fr);
  grid-auto-flow: column;
  overflow: hidden;
}

.mobile-summary-strip__item {
  display: flex;
  min-width: 0;
  gap: var(--space-1);
  padding-inline: var(--space-2);
  align-items: baseline;
  justify-content: center;
}

.mobile-summary-strip__item + .mobile-summary-strip__item {
  border-left: var(--border-width) solid var(--border-subtle);
}

.mobile-summary-strip__item dt,
.mobile-summary-strip__item dd {
  min-width: 0;
  margin: 0;
}

.mobile-summary-strip__item dt {
  overflow: hidden;
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
  line-height: var(--line-height-caption);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-summary-strip__item dd {
  flex: none;
  overflow: hidden;
  color: var(--text-primary);
  font-size: var(--font-size-title);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-title);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-summary-strip__item--primary dd {
  color: var(--color-primary);
}

.mobile-summary-strip__item--success dd {
  color: var(--status-success);
}

.mobile-summary-strip__item--muted dd {
  color: var(--text-secondary);
}
</style>
