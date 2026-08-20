<script setup lang="ts">
import { computed } from 'vue'

import type { ResolvedTheme } from '@/stores/theme'

import type {
  ActorAssetProvider,
  DeviceOfficeAssetBundle,
} from '../assets/device-office-assets'
import {
  WORKSTATION_FX_LAYOUT,
  type WorkstationSlot as WorkstationSlotLayout,
} from '../model/office-layout'
import type { OfficeStationViewModel } from '../model/types'
import ActorLayer from './ActorLayer.vue'
import DeskBaseLayer from './DeskBaseLayer.vue'
import DeviceLabelLayer from './DeviceLabelLayer.vue'
import ForegroundMaskLayer from './ForegroundMaskLayer.vue'
import FxLayer from './FxLayer.vue'
import InteractionHotspot from './InteractionHotspot.vue'
import LightOverlayLayer from './LightOverlayLayer.vue'
import ScreenLayer from './ScreenLayer.vue'

const props = defineProps<{
  station: OfficeStationViewModel
  layout: WorkstationSlotLayout
  theme: ResolvedTheme
  assets: DeviceOfficeAssetBundle
  actorProvider: ActorAssetProvider
}>()
defineEmits<{ select: [station: OfficeStationViewModel] }>()

const themeAssets = computed(() => props.assets.themes[props.theme])
const actorSource = computed(() => {
  if (!props.station.actorState || !props.station.actorVariant) return null
  return props.actorProvider.resolve({
    actorState: props.station.actorState,
    accentVariant: props.station.actorVariant.accentVariant,
  })
})
const screenSource = computed(() =>
  props.station.visualState === 'empty'
    ? null
    : props.assets.screens[props.station.visualState],
)
const fxSource = computed(() => {
  if (
    props.station.visualState !== 'offline' &&
    props.station.visualState !== 'error'
  ) {
    return null
  }
  return props.assets.fx[props.station.visualState]
})
const fxRect = computed(() => {
  if (
    props.station.visualState !== 'offline' &&
    props.station.visualState !== 'error'
  ) {
    return null
  }
  return WORKSTATION_FX_LAYOUT[props.station.visualState]
})
</script>

<template>
  <div
    class="workstation-slot"
    :class="`is-${station.visualState}`"
    :style="{
      left: `${layout.stationRect.x}px`,
      top: `${layout.stationRect.y}px`,
      width: `${layout.stationRect.width}px`,
      height: `${layout.stationRect.height}px`,
      zIndex: layout.zIndex,
    }"
    :data-testid="`office-slot-${station.slot}`"
    :data-slot-id="station.slot"
    :data-visual-state="station.visualState"
    :data-desk-asset="themeAssets.deskBase.src"
    :data-mask-asset="themeAssets.foregroundMask.src"
  >
    <DeskBaseLayer :source="themeAssets.deskBase" />
    <ScreenLayer
      v-if="screenSource && station.visualState !== 'empty'"
      :source="screenSource"
      :visual-state="station.visualState"
    />
    <ActorLayer
      v-if="actorSource && station.actorState"
      :source="actorSource"
      :actor-state="station.actorState"
    />
    <ForegroundMaskLayer :source="themeAssets.foregroundMask" />
    <LightOverlayLayer :source="themeAssets.lightOverlay" :theme="theme" />
    <FxLayer
      v-if="
        fxSource &&
        fxRect &&
        (station.visualState === 'offline' || station.visualState === 'error')
      "
      :source="fxSource"
      :rect="fxRect"
      :visual-state="station.visualState"
    />
    <InteractionHotspot
      :station="station"
      :rect="layout.hotspot"
      @select="$emit('select', $event)"
    />
    <DeviceLabelLayer
      :station="station"
      :anchor="layout.labelAnchor"
      @select="$emit('select', $event)"
    />
  </div>
</template>
