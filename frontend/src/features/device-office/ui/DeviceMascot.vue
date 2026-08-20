<script setup lang="ts">
import { computed, inject, onUnmounted, shallowRef } from 'vue'
import { Euler, Group, MathUtils, MeshStandardMaterial, Vector3 } from 'three'
import { useLoop } from '@tresjs/core'

import type {
  DeviceMascotVariant,
  DeviceVisualState,
  OfficeStationViewModel,
} from '../model/types'
import {
  OFFICE_RESOURCES_KEY,
  type OfficeResources,
} from './office-resources'

const props = defineProps<{
  station: OfficeStationViewModel
  home: [number, number, number]
  coffee: [number, number, number]
  visualState: Exclude<DeviceVisualState, 'empty'>
  variant: DeviceMascotVariant
}>()

const emit = defineEmits<{ select: [station: OfficeStationViewModel] }>()
const resources = inject<OfficeResources>(OFFICE_RESOURCES_KEY)
if (!resources) throw new Error('Office resources are not available')

const root = shallowRef<Group | null>(null)
const leftArm = shallowRef<Group | null>(null)
const rightArm = shallowRef<Group | null>(null)
const leftLeg = shallowRef<Group | null>(null)
const rightLeg = shallowRef<Group | null>(null)
const bodyMaterial = new MeshStandardMaterial({
  color: props.variant.bodyColor,
  roughness: 0.82,
})
const accentMaterial = new MeshStandardMaterial({
  color: props.variant.accentColor,
  roughness: 0.76,
})
const eyeMaterial = new MeshStandardMaterial({ color: '#20262c', roughness: 0.7 })
const target = new Vector3(...props.home)
let behavior: 'idle' | 'walk' | 'coffee' = 'idle'
let nextBehaviorAt = 20 + props.variant.index * 3

const isSleeping = computed(() => props.visualState === 'offline')
const isWorking = computed(() => props.visualState === 'busy')
const vector = (x: number, y: number, z: number) => new Vector3(x, y, z)
const asVector = (value: readonly number[]) =>
  new Vector3(value[0]!, value[1]!, value[2]!)
const rotation = (x: number, y: number, z: number) => new Euler(x, y, z)
onUnmounted(() => {
  bodyMaterial.dispose()
  accentMaterial.dispose()
  eyeMaterial.dispose()
})

function chooseIdleBehavior(elapsed: number): void {
  if (elapsed < nextBehaviorAt) return
  const choices = ['idle', 'walk', 'coffee'] as const
  behavior = choices[Math.floor(Math.random() * choices.length)]!
  nextBehaviorAt = elapsed + 20 + Math.random() * 30
}

useLoop().onBeforeRender(({ delta, elapsed }) => {
  if (!root.value) return
  if (props.visualState === 'onlineIdle') chooseIdleBehavior(elapsed)
  else behavior = 'idle'

  if (props.visualState === 'busy' || props.visualState === 'offline') {
    target.set(props.home[0], props.home[1] - 0.2, props.home[2])
  } else if (props.visualState === 'onlineIdle' && behavior === 'coffee') {
    target.set(...props.coffee)
  } else if (props.visualState === 'onlineIdle' && behavior === 'walk') {
    target.set(props.home[0] + 0.72, props.home[1], props.home[2] + 0.42)
  } else {
    target.set(...props.home)
  }

  root.value.position.lerp(target, Math.min(1, delta * 1.1))
  const moving = root.value.position.distanceToSquared(target) > 0.03
  const stride = moving ? Math.sin(elapsed * 8) * 0.48 : 0
  const workTap = isWorking.value ? Math.sin(elapsed * 12) * 0.22 : 0
  const armTarget = isWorking.value ? -0.92 + workTap : stride
  const legTarget = isSleeping.value ? 0 : -stride

  if (leftArm.value && rightArm.value) {
    leftArm.value.rotation.x = MathUtils.lerp(
      leftArm.value.rotation.x,
      armTarget,
      Math.min(1, delta * 7),
    )
    rightArm.value.rotation.x = MathUtils.lerp(
      rightArm.value.rotation.x,
      isWorking.value ? -0.92 - workTap : -stride,
      Math.min(1, delta * 7),
    )
  }
  if (leftLeg.value && rightLeg.value) {
    leftLeg.value.rotation.x = MathUtils.lerp(
      leftLeg.value.rotation.x,
      legTarget,
      Math.min(1, delta * 7),
    )
    rightLeg.value.rotation.x = MathUtils.lerp(
      rightLeg.value.rotation.x,
      -legTarget,
      Math.min(1, delta * 7),
    )
  }

  const desiredTilt = isSleeping.value ? 0.72 : 0
  root.value.rotation.z = MathUtils.lerp(
    root.value.rotation.z,
    desiredTilt,
    Math.min(1, delta * 4),
  )
  root.value.rotation.y =
    props.visualState === 'error' ? Math.sin(elapsed * 8) * 0.06 : 0
  root.value.scale.y = MathUtils.lerp(
    root.value.scale.y,
    isWorking.value ? 0.86 : 1,
    Math.min(1, delta * 4),
  )
})
</script>

<template>
  <TresGroup
    ref="root"
    :position="asVector(home)"
    @click.stop="emit('select', station)"
  >
    <TresMesh
      :geometry="resources.geometries.sphere"
      :material="bodyMaterial"
      :position="vector(0, 0.86, 0)"
      :scale="vector(0.92, 1.16, 0.78)"
    />
    <TresMesh
      :geometry="resources.geometries.sphere"
      :material="bodyMaterial"
      :position="vector(0, 1.78, -0.02)"
      :scale="vector(1.08, 0.98, 0.9)"
    />
    <TresMesh
      v-for="side in [-1, 1]"
      :key="`ear-${side}`"
      :geometry="resources.geometries.sphere"
      :material="accentMaterial"
      :position="vector(side * 0.43, 2.18, -0.02)"
      :scale="vector(0.35, 0.46, 0.3)"
    />
    <TresMesh
      v-for="side in [-1, 1]"
      :key="`eye-${side}`"
      :geometry="resources.geometries.sphere"
      :material="eyeMaterial"
      :position="vector(side * 0.2, 1.86, -0.43)"
      :scale="vector(0.1, 0.13, 0.08)"
    />

    <TresGroup ref="leftArm" :position="vector(-0.53, 1.08, 0)">
      <TresMesh
        :geometry="resources.geometries.cylinder"
        :material="bodyMaterial"
        :rotation="rotation(0, 0, -0.28)"
        :scale="vector(0.22, 0.82, 0.22)"
      />
    </TresGroup>
    <TresGroup ref="rightArm" :position="vector(0.53, 1.08, 0)">
      <TresMesh
        :geometry="resources.geometries.cylinder"
        :material="bodyMaterial"
        :rotation="rotation(0, 0, 0.28)"
        :scale="vector(0.22, 0.82, 0.22)"
      />
    </TresGroup>
    <TresGroup ref="leftLeg" :position="vector(-0.25, 0.18, 0)">
      <TresMesh
        :geometry="resources.geometries.cylinder"
        :material="bodyMaterial"
        :scale="vector(0.25, 0.55, 0.25)"
      />
    </TresGroup>
    <TresGroup ref="rightLeg" :position="vector(0.25, 0.18, 0)">
      <TresMesh
        :geometry="resources.geometries.cylinder"
        :material="bodyMaterial"
        :scale="vector(0.25, 0.55, 0.25)"
      />
    </TresGroup>

    <TresMesh
      v-if="variant.accessory === 'scarf'"
      :geometry="resources.geometries.torus"
      :material="accentMaterial"
      :position="vector(0, 1.42, -0.02)"
      :rotation="rotation(1.57, 0, 0)"
      :scale="vector(0.58, 0.58, 0.58)"
    />
    <TresMesh
      v-else-if="variant.accessory === 'badge'"
      :geometry="resources.geometries.box"
      :material="accentMaterial"
      :position="vector(0.22, 0.95, -0.43)"
      :scale="vector(0.28, 0.32, 0.08)"
    />
    <TresGroup v-else :position="vector(0, 2.38, 0)">
      <TresMesh
        :geometry="resources.geometries.cylinder"
        :material="accentMaterial"
        :scale="vector(0.08, 0.34, 0.08)"
      />
      <TresMesh
        :geometry="resources.geometries.sphere"
        :material="accentMaterial"
        :position="vector(0, 0.22, 0)"
        :scale="vector(0.2, 0.2, 0.2)"
      />
    </TresGroup>
  </TresGroup>
</template>
