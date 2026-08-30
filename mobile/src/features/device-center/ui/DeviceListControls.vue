<script setup lang="ts">
import { MobileSearchField } from '@/shared/ui'

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
</script>

<template>
  <section
    class="device-list-controls"
    aria-label="设备列表工具"
    data-testid="device-list-controls"
  >
    <MobileSearchField
      :model-value="searchQuery"
      :disabled="!searchAvailable"
      placeholder="搜索设备"
      aria-label="搜索设备"
      data-testid="device-search"
      @update:model-value="emit('updateSearchQuery', $event)"
    />

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
</style>
