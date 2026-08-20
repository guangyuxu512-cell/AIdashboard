import {
  CanvasTexture,
  LinearFilter,
  MeshStandardMaterial,
  SRGBColorSpace,
} from 'three'
import { markRaw, onUnmounted, watch, type Ref } from 'vue'
import { useLoop } from '@tresjs/core'

import type { DeviceVisualState } from '../model/types'

const SCREEN_COLORS: Record<DeviceVisualState, [string, string]> = {
  empty: ['#172028', '#63717d'],
  onlineIdle: ['#183343', '#70a8b0'],
  busy: ['#172c3c', '#84b9c8'],
  offline: ['#090c0f', '#20262b'],
  error: ['#351d22', '#d18078'],
}

export function useDeviceScreenTexture(state: Ref<DeviceVisualState>) {
  const canvas = document.createElement('canvas')
  canvas.width = 256
  canvas.height = 128
  const context = canvas.getContext('2d')
  const texture = markRaw(new CanvasTexture(canvas))
  texture.colorSpace = SRGBColorSpace
  texture.minFilter = LinearFilter
  texture.magFilter = LinearFilter
  const material = markRaw(
    new MeshStandardMaterial({
      color: '#ffffff',
      emissive: '#ffffff',
      emissiveIntensity: 0.42,
      map: texture,
      emissiveMap: texture,
      roughness: 0.5,
    }),
  )
  let elapsedSinceDraw = 1
  let phase = 0

  function draw(): void {
    if (!context) return
    const [background, accent] = SCREEN_COLORS[state.value]
    context.fillStyle = background
    context.fillRect(0, 0, canvas.width, canvas.height)
    if (state.value === 'offline') {
      texture.needsUpdate = true
      return
    }

    context.fillStyle = accent
    context.globalAlpha = state.value === 'empty' ? 0.28 : 0.72
    context.fillRect(18, 18, 84, 10)
    context.fillRect(18, 38, 54, 7)
    context.globalAlpha = 0.18
    for (let row = 0; row < 3; row += 1) {
      const width = 72 + ((phase + row * 29) % 102)
      context.fillRect(18, 62 + row * 16, width, 8)
    }
    if (state.value === 'error') {
      context.globalAlpha = 0.9
      context.font = 'bold 34px sans-serif'
      context.fillText('!', 214, 52)
    }
    context.globalAlpha = 1
    phase = (phase + 7) % 103
    texture.needsUpdate = true
  }

  draw()
  watch(state, draw)
  useLoop().onBeforeRender(({ delta }) => {
    elapsedSinceDraw += delta
    if (elapsedSinceDraw < 0.125) return
    elapsedSinceDraw = 0
    draw()
  })

  onUnmounted(() => {
    texture.dispose()
    material.dispose()
  })

  return material
}
