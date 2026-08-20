<script setup lang="ts">
import { computed, onMounted, ref, shallowRef } from 'vue'

import type { ResolvedTheme } from '@/stores/theme'

import {
  ART_ASSETS_PENDING,
  loadDeviceOfficeAssetManifest,
  ManifestActorAssetProvider,
  REFERENCE_PREVIEW_MODE,
  type DeviceOfficeAssetManifest,
} from '../assets/device-office-assets'
import type { OfficeStationViewModel } from '../model/types'
import BackEnvironment from './BackEnvironment.vue'
import DeviceActorLayer from './DeviceActorLayer.vue'
import DeviceLabels from './DeviceLabels.vue'
import ForegroundOcclusion from './ForegroundOcclusion.vue'
import InteractionHotspots from './InteractionHotspots.vue'
import MonitorScreenLayer from './MonitorScreenLayer.vue'
import OfficeBackground from './OfficeBackground.vue'
import { useFixedStageScale } from './use-fixed-stage-scale'
import './device-office-stage.css'

const props = defineProps<{
  stations: OfficeStationViewModel[]
  resolvedTheme: ResolvedTheme
}>()

defineEmits<{ select: [station: OfficeStationViewModel] }>()

const host = ref<HTMLElement | null>(null)
const manifest = shallowRef<DeviceOfficeAssetManifest | null>(null)
const manifestError = ref('')
const { scale } = useFixedStageScale(host)

const sceneAssets = computed(() =>
  manifest.value ? manifest.value.scene[props.resolvedTheme] : null,
)
const referenceSource = computed(() =>
  import.meta.env.DEV && manifest.value
    ? manifest.value.referencePreview[props.resolvedTheme]
    : null,
)
const referencePreview = computed(
  () => props.resolvedTheme === 'dark' && referenceSource.value !== null,
)
const backgroundSource = computed(
  () => sceneAssets.value?.background ?? referenceSource.value,
)
const actorProvider = computed(() =>
  manifest.value ? new ManifestActorAssetProvider(manifest.value) : null,
)
const stageMode = computed(() => {
  if (referencePreview.value) return REFERENCE_PREVIEW_MODE
  if (manifest.value?.status === 'READY') return 'READY'
  return ART_ASSETS_PENDING
})

onMounted(async () => {
  try {
    manifest.value = await loadDeviceOfficeAssetManifest()
  } catch (error) {
    manifestError.value =
      error instanceof Error
        ? error.message
        : 'Device Office asset manifest error'
  }
})
</script>

<template>
  <section
    ref="host"
    class="device-office-stage"
    :class="`device-office-stage--${resolvedTheme}`"
    aria-label="设备 2.5D 办公区"
    data-testid="device-office-stage"
    :data-stage-mode="stageMode"
  >
    <div
      class="device-office-stage__canvas"
      :style="{ '--office-stage-scale': scale }"
    >
      <OfficeBackground :source="backgroundSource" />
      <BackEnvironment :source="sceneAssets?.backEnvironment ?? null" />
      <DeviceActorLayer
        v-if="actorProvider"
        :stations="stations"
        :provider="actorProvider"
      />
      <MonitorScreenLayer
        v-if="manifest"
        :stations="stations"
        :manifest="manifest"
      />
      <ForegroundOcclusion :source="sceneAssets?.foreground ?? null" />
      <DeviceLabels :stations="stations" @select="$emit('select', $event)" />
      <InteractionHotspots
        :stations="stations"
        :reference-preview="referencePreview"
        @select="$emit('select', $event)"
      />

      <div class="device-office-stage__status" aria-live="polite">
        <span class="device-office-stage__badge">{{ stageMode }}</span>
        <span
          v-if="referencePreview && manifest?.status === ART_ASSETS_PENDING"
          class="device-office-stage__badge"
        >
          ART ASSETS PENDING
        </span>
      </div>

      <div
        v-if="
          manifestError || (!referencePreview && manifest?.status !== 'READY')
        "
        class="device-office-stage__missing"
        role="status"
      >
        <strong>
          {{
            manifestError ||
            (resolvedTheme === 'light'
              ? 'Light office artwork pending'
              : 'Dark office artwork pending')
          }}
        </strong>
        <span>正式办公室、人物动画与前景遮挡美术尚未交付</span>
      </div>
    </div>
  </section>
</template>
