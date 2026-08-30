<script setup lang="ts">
import { Button as VanButton } from 'vant'

import { MobileIcon } from '@/shared/icons'

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
        <span class="mobile-list-toolbar__control">
          <span class="mobile-list-toolbar__control-label">
            {{ selectorLabel }}
          </span>
          <MobileIcon name="arrow-down" />
        </span>
      </VanButton>
      <VanButton
        v-if="filterLabel"
        class="mobile-list-toolbar__action"
        :aria-label="filterAriaLabel || filterLabel"
        data-testid="mobile-list-filter"
        @click="emit('filter')"
      >
        <span class="mobile-list-toolbar__control">
          <MobileIcon name="filter" />
          <span class="mobile-list-toolbar__control-label">
            {{ filterLabel }}
          </span>
        </span>
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
  gap: var(--layout-toolbar-group-gap);
  padding-right: max(var(--layout-page-padding-x), var(--safe-area-right));
  padding-left: max(var(--layout-page-padding-x), var(--safe-area-left));
  align-items: center;
  background: var(--bg-app);
}

.mobile-list-toolbar__identity {
  display: flex;
  min-width: 0;
  flex: 1 1 auto;
  gap: var(--layout-toolbar-inner-gap);
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
  gap: var(--layout-toolbar-inner-gap);
  align-items: center;
}

.mobile-list-toolbar__action {
  min-width: var(--touch-target-min);
  height: var(--touch-target-min);
  padding: 0;
  color: var(--text-secondary);
  background: transparent;
  border: 0;
}

.mobile-list-toolbar__selector {
  max-width: calc(var(--touch-target-min) + var(--touch-target-min));
}

.mobile-list-toolbar__action :deep(.van-button__content) {
  width: 100%;
  min-width: 0;
}

.mobile-list-toolbar__control {
  display: inline-flex;
  width: 100%;
  min-width: 0;
  height: var(--control-height-compact);
  gap: var(--layout-toolbar-inner-gap);
  padding-inline: var(--layout-toolbar-control-padding-x);
  align-items: center;
  justify-content: center;
  background: var(--bg-surface);
  border: var(--border-width) solid transparent;
  border-radius: var(--radius-control);
  box-shadow: var(--appearance-border-control);
}

.mobile-list-toolbar__action:active .mobile-list-toolbar__control {
  background: var(--bg-surface-pressed);
  border-color: var(--border-default);
}

.mobile-list-toolbar__control-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-list-toolbar__control .mobile-icon {
  font-size: var(--icon-size-small);
}
</style>
