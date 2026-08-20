<script setup lang="ts">
import { onUnmounted, provide, watch } from 'vue'
import { Euler, Vector3 } from 'three'
import { useLoop } from '@tresjs/core'

import type { OfficeStationViewModel } from '../model/types'
import type { OfficeSceneTheme } from '../theme/office-scene-theme'
import DeviceMascot from './DeviceMascot.vue'
import Workstation from './Workstation.vue'
import {
  createOfficeResources,
  OFFICE_RESOURCES_KEY,
} from './office-resources'

const props = defineProps<{
  stations: OfficeStationViewModel[]
  theme: OfficeSceneTheme
}>()

const emit = defineEmits<{
  select: [station: OfficeStationViewModel]
  performance: [fps: number]
}>()
const resources = createOfficeResources(props.theme)
provide(OFFICE_RESOURCES_KEY, resources)

const workstationPositions: [number, number, number][] = Array.from(
  { length: 9 },
  (_, index) => [((index % 3) - 1) * 4.7, 0, (Math.floor(index / 3) - 1) * 4.25],
)
const plantPositions = [
  [-7.2, 0, -5.7],
  [7.4, 0, 5.3],
] as const
const vector = (x: number, y: number, z: number) => new Vector3(x, y, z)
const asVector = (value: readonly number[]) =>
  new Vector3(value[0]!, value[1]!, value[2]!)
const rotation = (x: number, y: number, z: number) => new Euler(x, y, z)
let sampleSeconds = 0
let sampleFrames = 0
useLoop().onBeforeRender(({ delta }) => {
  sampleSeconds += delta
  sampleFrames += 1
  if (sampleSeconds < 1) return
  emit('performance', Math.round(sampleFrames / sampleSeconds))
  sampleSeconds = 0
  sampleFrames = 0
})

watch(
  () => props.theme,
  (theme) => resources.update(theme),
)
onUnmounted(resources.dispose)
</script>

<template>
  <TresPerspectiveCamera
    :position="vector(0, 14.2, 17.8)"
    :look-at="vector(0, 0.7, 0)"
    :fov="40"
  />
  <TresAmbientLight
    :color="theme.ambientLight"
    :intensity="theme.ambientLightIntensity"
  />
  <TresDirectionalLight
    :position="vector(-4, 11, 8)"
    :color="theme.mainLight"
    :intensity="theme.mainLightIntensity"
    cast-shadow
  />
  <TresPointLight
    :position="vector(7, 4.8, -5.5)"
    :color="theme.accentLight"
    :intensity="theme.accentLightIntensity"
    :distance="10"
  />

  <TresMesh
    :geometry="resources.geometries.plane"
    :material="resources.materials.floor"
    :rotation="rotation(-1.5708, 0, 0)"
    :scale="vector(18, 15.5, 1)"
    receive-shadow
  />
  <TresMesh
    :geometry="resources.geometries.box"
    :material="resources.materials.wall"
    :position="vector(0, 3.3, -7.6)"
    :scale="vector(18, 6.6, 0.18)"
  />

  <Workstation
    v-for="(station, index) in stations"
    :key="station.device?.deviceId ?? `empty-${station.slot}`"
    :station="station"
    :position="workstationPositions[index]!"
    @select="emit('select', $event)"
  />

  <DeviceMascot
    v-for="(station, index) in stations.filter((item) => item.device)"
    :key="station.device!.deviceId"
    :station="station"
    :home="[
      workstationPositions[stations.indexOf(station)]![0],
      0.45,
      workstationPositions[stations.indexOf(station)]![2] + 0.72,
    ]"
    :coffee="[7.05 + (index % 2) * 0.45, 0.45, -5.15 + (index % 3) * 0.35]"
    :visual-state="station.visualState as Exclude<typeof station.visualState, 'empty'>"
    :variant="station.mascotVariant!"
    @select="emit('select', $event)"
  />

  <TresGroup :position="vector(7.1, 0, -5.45)">
    <TresMesh
      :geometry="resources.geometries.box"
      :material="resources.materials.desk"
      :position="vector(0, 0.75, 0)"
      :scale="vector(2.3, 1.45, 1.1)"
    />
    <TresMesh
      :geometry="resources.geometries.cylinder"
      :material="resources.materials.monitor"
      :position="vector(-0.42, 1.68, 0)"
      :scale="vector(0.22, 0.58, 0.22)"
    />
    <TresMesh
      :geometry="resources.geometries.cylinder"
      :material="resources.materials.monitor"
      :position="vector(0.38, 1.58, 0)"
      :scale="vector(0.32, 0.4, 0.32)"
    />
  </TresGroup>

  <TresGroup
    v-for="position in plantPositions"
    :key="position.join('-')"
    :position="asVector(position)"
  >
    <TresMesh
      :geometry="resources.geometries.cylinder"
      :material="resources.materials.planter"
      :position="vector(0, 0.45, 0)"
      :scale="vector(0.62, 0.9, 0.62)"
    />
    <TresMesh
      v-for="offset in [-0.34, 0, 0.34]"
      :key="offset"
      :geometry="resources.geometries.sphere"
      :material="resources.materials.plant"
      :position="vector(offset, 1.36 + Math.abs(offset), 0)"
      :scale="vector(0.66, 1.05, 0.66)"
    />
  </TresGroup>
</template>
