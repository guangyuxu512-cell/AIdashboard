<script setup lang="ts">
import { computed, inject } from 'vue'
import { Euler, Vector3 } from 'three'

import type { OfficeStationViewModel } from '../model/types'
import {
  OFFICE_RESOURCES_KEY,
  type OfficeResources,
} from './office-resources'
import { useDeviceScreenTexture } from './useDeviceScreenTexture'

const props = defineProps<{
  station: OfficeStationViewModel
  position: [number, number, number]
}>()
defineOptions({ name: 'OfficeWorkstation' })

const emit = defineEmits<{ select: [station: OfficeStationViewModel] }>()
const resources = inject<OfficeResources>(OFFICE_RESOURCES_KEY)
if (!resources) throw new Error('Office resources are not available')

const visualState = computed(() => props.station.visualState)
const screenMaterial = useDeviceScreenTexture(visualState)
const monitorGlow = computed(() => props.station.visualState !== 'offline')
const vector = (x: number, y: number, z: number) => new Vector3(x, y, z)
const asVector = (value: readonly number[]) =>
  new Vector3(value[0]!, value[1]!, value[2]!)
const rotation = (x: number, y: number, z: number) => new Euler(x, y, z)

function select(): void {
  if (props.station.device) emit('select', props.station)
}
</script>

<template>
  <TresGroup :position="asVector(position)" @click.stop="select">
    <TresMesh
      :geometry="resources.geometries.box"
      :material="resources.materials.desk"
      :position="vector(0, 1.05, 0)"
      :scale="vector(3.1, 0.18, 1.45)"
      receive-shadow
    />
    <TresMesh
      v-for="leg in [
        [-1.28, 0.53, -0.52],
        [1.28, 0.53, -0.52],
        [-1.28, 0.53, 0.52],
        [1.28, 0.53, 0.52],
      ]"
      :key="leg.join('-')"
      :geometry="resources.geometries.box"
      :material="resources.materials.desk"
      :position="asVector(leg)"
      :scale="vector(0.16, 1, 0.16)"
    />

    <TresMesh
      :geometry="resources.geometries.box"
      :material="resources.materials.monitor"
      :position="vector(0, 1.72, -0.28)"
      :scale="vector(1.45, 0.9, 0.12)"
    />
    <TresMesh
      :geometry="resources.geometries.plane"
      :material="screenMaterial"
      :position="vector(0, 1.72, -0.211)"
      :rotation="rotation(-0.08, 0, 0)"
      :scale="vector(1.25, 0.7, 1)"
    />
    <TresPointLight
      v-if="monitorGlow"
      :position="vector(0, 1.65, 0.18)"
      :color="station.visualState === 'error' ? '#bd6a68' : '#73a8b1'"
      :intensity="0.18"
      :distance="2.2"
    />
    <TresMesh
      :geometry="resources.geometries.box"
      :material="resources.materials.monitor"
      :position="vector(0, 1.28, -0.28)"
      :scale="vector(0.12, 0.42, 0.12)"
    />
    <TresMesh
      :geometry="resources.geometries.box"
      :material="resources.materials.monitor"
      :position="vector(0, 1.1, -0.22)"
      :scale="vector(0.65, 0.08, 0.38)"
    />

    <TresGroup :position="vector(0, 0.72, 1.08)">
      <TresMesh
        :geometry="resources.geometries.box"
        :material="resources.materials.chair"
        :position="vector(0, 0, 0)"
        :scale="vector(1.05, 0.18, 0.95)"
      />
      <TresMesh
        :geometry="resources.geometries.box"
        :material="resources.materials.chair"
        :position="vector(0, 0.72, 0.34)"
        :rotation="rotation(-0.12, 0, 0)"
        :scale="vector(1.05, 1.35, 0.16)"
      />
      <TresMesh
        :geometry="resources.geometries.cylinder"
        :material="resources.materials.chair"
        :position="vector(0, -0.4, 0)"
        :scale="vector(0.13, 0.72, 0.13)"
      />
    </TresGroup>
  </TresGroup>
</template>
