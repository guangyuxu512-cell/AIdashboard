<script setup lang="ts">
import { Button as VanButton, Icon as VanIcon } from 'vant'

withDefaults(
  defineProps<{
    title: string
    meta?: string
    selectorLabel?: string
    selectorAriaLabel?: string
    filterLabel?: string
    filterAriaLabel?: string
  }>(),
  {
    meta: undefined,
    selectorLabel: undefined,
    selectorAriaLabel: undefined,
    filterLabel: undefined,
    filterAriaLabel: undefined,
  },
)

const emit = defineEmits<{
  selector: []
  filter: []
}>()
</script>

<template>
  <div class="mobile-list-toolbar" data-testid="mobile-list-toolbar">
    <div class="mobile-list-toolbar__identity">
      <h1>{{ title }}</h1>
      <span v-if="meta">{{ meta }}</span>
    </div>

    <div
      v-if="selectorLabel || filterLabel"
      class="mobile-list-toolbar__actions"
    >
      <VanButton
        v-if="selectorLabel"
        class="mobile-list-toolbar__action mobile-list-toolbar__selector"
        :aria-label="selectorAriaLabel || selectorLabel"
        data-testid="mobile-list-selector"
        @click="emit('selector')"
      >
        <span>{{ selectorLabel }}</span>
        <VanIcon name="arrow-down" aria-hidden="true" />
      </VanButton>
      <VanButton
        v-if="filterLabel"
        class="mobile-list-toolbar__action"
        icon="filter-o"
        :aria-label="filterAriaLabel || filterLabel"
        data-testid="mobile-list-filter"
        @click="emit('filter')"
      >
        {{ filterLabel }}
      </VanButton>
    </div>
  </div>
</template>

<style scoped>
.mobile-list-toolbar {
  display: flex;
  width: 100%;
  min-width: 0;
  height: var(--layout-toolbar-height);
  flex: none;
  gap: var(--space-2);
  padding-right: max(var(--layout-page-padding-x), var(--safe-area-right));
  padding-left: max(var(--layout-page-padding-x), var(--safe-area-left));
  align-items: center;
  background: var(--bg-app);
}

.mobile-list-toolbar__identity {
  display: flex;
  min-width: 0;
  flex: 1 1 auto;
  gap: var(--space-1);
  align-items: baseline;
  overflow: hidden;
}

.mobile-list-toolbar__identity h1 {
  flex: none;
  font-size: var(--font-size-label);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-label);
}

.mobile-list-toolbar__identity span {
  overflow: hidden;
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-list-toolbar__actions {
  display: flex;
  min-width: 0;
  flex: none;
  gap: var(--space-1);
  align-items: center;
}

.mobile-list-toolbar__action {
  height: var(--touch-target-min);
  padding-inline: var(--space-2);
  color: var(--text-secondary);
  background: var(--bg-surface);
  border-color: var(--border-subtle);
}

.mobile-list-toolbar__selector {
  max-width: calc(var(--touch-target-min) + var(--touch-target-min));
}

.mobile-list-toolbar__selector :deep(.van-button__content) {
  min-width: 0;
  gap: var(--space-1);
}

.mobile-list-toolbar__selector span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
