<script setup lang="ts">
import { useDocumentVisibility } from '@vueuse/core'
import { computed, onMounted, ref, shallowRef, watch } from 'vue'

import type { ResolvedTheme } from '@/stores/theme'

import {
  createDeviceOfficeAssetBundle,
  loadDeviceOfficeAssetManifest,
  ManifestActorAssetProvider,
  preloadDeviceOfficeTheme,
  type DeviceOfficeAssetBundle,
  type DeviceOfficeAssetManifest,
} from '../assets/device-office-assets'
import { WORKSTATION_SLOTS } from '../model/office-layout'
import type { OfficeStationViewModel } from '../model/types'
import OfficeBackgroundLayer from './OfficeBackgroundLayer.vue'
import { useFixedStageScale } from './use-fixed-stage-scale'
import WorkstationSlot from './WorkstationSlot.vue'
import './device-office-stage.css'

const props = defineProps<{
  stations: OfficeStationViewModel[]
  resolvedTheme: ResolvedTheme
}>()

defineEmits<{ select: [station: OfficeStationViewModel] }>()

const host = ref<HTMLElement | null>(null)
const manifest = shallowRef<DeviceOfficeAssetManifest | null>(null)
const assets = shallowRef<DeviceOfficeAssetBundle | null>(null)
const activeTheme = ref<ResolvedTheme>(props.resolvedTheme)
const assetsReady = ref(false)
const assetError = ref('')
const visibility = useDocumentVisibility()
const { scale } = useFixedStageScale(host)
let themeRequestId = 0

const actorProvider = computed(() =>
  assets.value ? new ManifestActorAssetProvider(assets.value) : null,
)
const animationsPaused = computed(() => visibility.value === 'hidden')

async function activateTheme(
  theme: ResolvedTheme,
  bundle: DeviceOfficeAssetBundle,
): Promise<void> {
  const requestId = ++themeRequestId
  assetError.value = ''
  try {
    await preloadDeviceOfficeTheme(bundle.themes[theme])
    if (requestId !== themeRequestId) return
    activeTheme.value = theme
    assetsReady.value = true
  } catch (error) {
    if (requestId !== themeRequestId) return
    assetError.value =
      error instanceof Error ? error.message : '设备办公区美术资源加载失败'
  }
}

onMounted(async () => {
  try {
    const loadedManifest = await loadDeviceOfficeAssetManifest()
    const loadedAssets = createDeviceOfficeAssetBundle(loadedManifest)
    manifest.value = loadedManifest
    assets.value = loadedAssets
    await activateTheme(props.resolvedTheme, loadedAssets)
  } catch (error) {
    assetError.value =
      error instanceof Error ? error.message : '设备办公区美术资源加载失败'
  }
})

watch(
  () => props.resolvedTheme,
  (theme) => {
    if (assets.value) {
      void activateTheme(theme, assets.value)
    }
  },
)
</script>

<template>
  <section
    ref="host"
    class="device-office-stage"
    :class="`device-office-stage--${activeTheme}`"
    aria-label="设备 2.5D 办公区"
    :aria-busy="!assetsReady"
    data-testid="device-office-stage"
    :data-stage-mode="assetError ? 'error' : assetsReady ? 'ready' : 'loading'"
    :data-asset-version="manifest?.version"
  >
    <div
      class="device-office-stage__canvas"
      :class="{ 'is-animation-paused': animationsPaused }"
      :style="{ '--office-stage-scale': scale }"
    >
      <template v-if="assets && actorProvider && assetsReady">
        <OfficeBackgroundLayer
          :source="assets.themes[activeTheme].background"
        />
        <WorkstationSlot
          v-for="station in stations"
          :key="station.slot"
          :station="station"
          :layout="WORKSTATION_SLOTS[station.slot - 1]!"
          :theme="activeTheme"
          :assets="assets"
          :actor-provider="actorProvider"
          @select="$emit('select', $event)"
        />
      </template>

      <div
        v-if="!assetsReady"
        class="device-office-stage__loading"
        role="status"
      >
        <strong>{{ assetError || '正在加载办公区美术资源…' }}</strong>
        <span v-if="assetError">请重新加载页面后再试</span>
      </div>
    </div>
  </section>
</template>
