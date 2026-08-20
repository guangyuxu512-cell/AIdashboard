<script setup lang="ts">
import { computed } from 'vue'

import type {
  ActorAssetProvider,
  DeviceOfficeAssetSource,
} from '../assets/device-office-assets'
import type { OfficePoint } from '../model/office-layout'
import type { DeviceAccentVariant, DeviceActorState } from '../model/types'
import OfficeVisualAsset from './OfficeVisualAsset.vue'

const props = defineProps<{
  actorState: DeviceActorState
  accentVariant: DeviceAccentVariant
  position: OfficePoint
  scale: number
  zIndex: number
  provider: ActorAssetProvider
}>()

const source = computed<DeviceOfficeAssetSource | null>(() =>
  props.provider.resolve({
    actorState: props.actorState,
    accentVariant: props.accentVariant,
  }),
)

const style = computed(() => ({
  left: `${props.position.x}px`,
  top: `${props.position.y}px`,
  zIndex: props.zIndex,
  transform: `translate(-50%, -100%) scale(${props.scale})`,
}))
</script>

<template>
  <div
    class="mascot-actor"
    :style="style"
    :data-actor-state="actorState"
    :data-accent-variant="accentVariant"
    :data-asset-status="source ? 'ready' : 'missing'"
    aria-hidden="true"
  >
    <OfficeVisualAsset
      v-if="source"
      :source="source"
      asset-class="mascot-actor__asset"
    />
  </div>
</template>
