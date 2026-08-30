<script setup lang="ts">
import { MobileIcon } from '@/shared/icons'

import type { DeviceOverview } from '../model/device-overview'
import type { DeviceQuickFilter } from '../model/device-filter'
import DeviceOverviewCards from './DeviceOverviewCards.vue'

defineProps<{
  overview: DeviceOverview
  filter: DeviceQuickFilter
  searchQuery: string
  searchAvailable: boolean
}>()

const emit = defineEmits<{
  selectFilter: [filter: DeviceQuickFilter]
  updateSearchQuery: [query: string]
}>()

function updateSearch(event: Event): void {
  emit('updateSearchQuery', (event.target as HTMLInputElement).value)
}
</script>

<template>
  <section
    class="device-list-controls"
    aria-label="设备列表工具"
    data-testid="device-list-controls"
  >
    <label
      class="device-list-controls__search"
      :class="{
        'device-list-controls__search--disabled': !searchAvailable,
      }"
    >
      <MobileIcon class="device-list-controls__search-icon" name="search" />
      <input
        type="search"
        :value="searchQuery"
        :disabled="!searchAvailable"
        placeholder="搜索设备"
        aria-label="搜索设备"
        autocomplete="off"
        data-testid="device-search"
        @input="updateSearch"
      />
    </label>

    <DeviceOverviewCards
      :overview="overview"
      :filter="filter"
      @select="emit('selectFilter', $event)"
    />
  </section>
</template>

<style scoped>
.device-list-controls {
  display: grid;
  width: 100%;
  min-width: 0;
  flex: none;
  gap: var(--device-list-fixed-controls-gap);
  padding: var(--device-list-fixed-padding-top)
    max(var(--device-list-page-padding-x), var(--safe-area-right))
    var(--device-list-fixed-padding-bottom)
    max(var(--device-list-page-padding-x), var(--safe-area-left));
}

.device-list-controls__search {
  display: flex;
  width: 100%;
  min-width: 0;
  height: var(--device-list-search-height);
  align-items: center;
  padding: 0 var(--device-list-search-padding-x);
  color: var(--device-list-search-color);
  background: var(--device-list-search-background);
  border: var(--device-list-search-border-width) solid
    var(--device-list-search-border);
  border-radius: var(--device-list-search-radius);
  box-shadow: var(--device-list-search-shadow);
}

.device-list-controls__search:focus-within {
  border-color: var(--focus-ring-color);
  box-shadow: 0 0 0 var(--focus-ring-width) var(--color-primary-soft);
}

.device-list-controls__search--disabled {
  color: var(--device-list-search-disabled-color);
}

.device-list-controls__search-icon {
  width: var(--device-list-search-icon-size);
  height: var(--device-list-search-icon-size);
  flex: none;
  font-size: var(--device-list-search-icon-size);
}

.device-list-controls__search input {
  width: 100%;
  min-width: 0;
  height: 100%;
  padding: 0 0 0 var(--device-list-search-icon-gap);
  color: var(--device-list-search-input-color);
  font-size: var(--device-list-search-font-size);
  font-weight: var(--device-list-search-font-weight);
  line-height: var(--device-list-search-line-height);
  appearance: none;
  background: transparent;
  border: 0;
  outline: 0;
}

.device-list-controls__search input::placeholder {
  color: var(--device-list-search-color);
  opacity: 1;
}

.device-list-controls__search input:disabled {
  cursor: default;
  opacity: 1;
}

.device-list-controls__search input::-webkit-search-cancel-button {
  appearance: none;
}
</style>
