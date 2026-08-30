<script setup lang="ts">
import type {
  DeviceArtworkKind,
  DeviceArtworkState,
} from '../model/device-artwork'

withDefaults(
  defineProps<{
    kind?: DeviceArtworkKind
    state: DeviceArtworkState
  }>(),
  { kind: 'desktop' },
)
</script>

<template>
  <span
    class="device-status-artwork"
    :class="[
      `device-status-artwork--${kind}`,
      `device-status-artwork--${state}`,
    ]"
    :data-device-artwork-kind="kind"
    :data-device-artwork-state="state"
    data-testid="device-status-artwork"
    aria-hidden="true"
  >
    <span v-if="kind === 'desktop'" class="device-status-artwork__desktop">
      <span class="device-status-artwork__screen">
        <span class="device-status-artwork__screen-glow" />
        <span class="device-status-artwork__screen-shine" />
        <span class="device-status-artwork__offline-mark" />
      </span>
      <span class="device-status-artwork__neck" />
      <span class="device-status-artwork__base" />
      <span class="device-status-artwork__corner" />
      <span class="device-status-artwork__pulse-ring" />
    </span>

    <span v-else-if="kind === 'laptop'" class="device-status-artwork__laptop">
      <span class="device-status-artwork__screen">
        <span class="device-status-artwork__screen-glow" />
        <span class="device-status-artwork__screen-shine" />
        <span class="device-status-artwork__offline-mark" />
      </span>
      <span class="device-status-artwork__laptop-body" />
      <span class="device-status-artwork__laptop-shadow" />
      <span class="device-status-artwork__corner" />
      <span class="device-status-artwork__pulse-ring" />
    </span>

    <span v-else class="device-status-artwork__server">
      <span class="device-status-artwork__server-vents" />
      <span class="device-status-artwork__server-leds">
        <i />
        <i />
        <i />
      </span>
      <span class="device-status-artwork__server-button" />
      <span class="device-status-artwork__corner" />
      <span class="device-status-artwork__pulse-ring" />
    </span>
  </span>
</template>

<style scoped>
.device-status-artwork {
  position: relative;
  display: grid;
  width: var(--device-list-artwork-width);
  height: var(--device-list-artwork-height);
  place-items: center;
}

.device-status-artwork__desktop,
.device-status-artwork__laptop,
.device-status-artwork__server {
  position: relative;
  filter: var(--device-artwork-shadow);
}

.device-status-artwork__desktop {
  width: var(--device-artwork-desktop-width);
  height: var(--device-artwork-desktop-height);
}

.device-status-artwork__desktop .device-status-artwork__screen {
  width: var(--device-artwork-desktop-width);
  height: var(--device-artwork-desktop-screen-height);
}

.device-status-artwork__screen {
  position: relative;
  display: block;
  overflow: hidden;
  background: var(--device-artwork-screen-neutral);
  border: var(--device-artwork-screen-border-width) solid
    var(--device-artwork-frame);
  border-radius: var(--device-artwork-screen-radius);
  box-shadow: var(--device-artwork-screen-inset);
}

.device-status-artwork__neck {
  position: absolute;
  top: var(--device-artwork-desktop-screen-height);
  left: var(--device-artwork-desktop-neck-left);
  width: var(--device-artwork-desktop-neck-width);
  height: var(--device-artwork-desktop-neck-height);
  background: var(--device-artwork-neck);
}

.device-status-artwork__base {
  position: absolute;
  top: var(--device-artwork-desktop-base-top);
  left: var(--device-artwork-desktop-base-left);
  width: var(--device-artwork-desktop-base-width);
  height: var(--device-artwork-desktop-base-height);
  background: var(--device-artwork-base);
  border-radius: var(--device-artwork-base-radius);
}

.device-status-artwork__laptop {
  width: var(--device-artwork-laptop-width);
  height: var(--device-artwork-laptop-height);
}

.device-status-artwork__laptop .device-status-artwork__screen {
  position: absolute;
  top: var(--device-artwork-laptop-screen-top);
  left: var(--device-artwork-laptop-screen-left);
  width: var(--device-artwork-laptop-screen-width);
  height: var(--device-artwork-laptop-screen-height);
}

.device-status-artwork__laptop-body {
  position: absolute;
  right: var(--device-artwork-laptop-body-inset);
  bottom: var(--device-artwork-laptop-body-bottom);
  left: var(--device-artwork-laptop-body-inset);
  height: var(--device-artwork-laptop-body-height);
  background: var(--device-artwork-laptop-body);
  border-radius: var(--device-artwork-laptop-body-radius);
  transform: perspective(var(--device-artwork-laptop-perspective))
    rotateX(var(--device-artwork-laptop-rotation));
}

.device-status-artwork__laptop-shadow {
  position: absolute;
  right: var(--device-artwork-laptop-shadow-inset);
  bottom: 0;
  left: var(--device-artwork-laptop-shadow-inset);
  height: var(--device-artwork-laptop-shadow-height);
  background: var(--device-artwork-ground-shadow);
  border-radius: 50%;
  filter: blur(var(--device-artwork-ground-shadow-blur));
}

.device-status-artwork__server {
  width: var(--device-artwork-server-width);
  height: var(--device-artwork-server-height);
  overflow: hidden;
  background: var(--device-artwork-server-neutral);
  border-radius: var(--device-artwork-server-radius);
  box-shadow: var(--device-artwork-server-inset);
}

.device-status-artwork__server-vents {
  position: absolute;
  top: var(--device-artwork-server-vents-top);
  right: var(--device-artwork-server-vents-inset);
  left: var(--device-artwork-server-vents-inset);
  height: var(--device-artwork-server-vents-height);
  background: var(--device-artwork-server-vents);
  border-radius: var(--device-artwork-server-vents-radius);
}

.device-status-artwork__server-leds {
  position: absolute;
  top: var(--device-artwork-server-leds-top);
  left: var(--device-artwork-server-leds-left);
  z-index: 2;
  display: flex;
  flex-direction: column;
  gap: var(--device-artwork-server-leds-gap);
}

.device-status-artwork__server-leds i {
  width: var(--device-artwork-server-led-size);
  height: var(--device-artwork-server-led-size);
  background: var(--device-artwork-server-led-neutral);
  border-radius: 50%;
  opacity: var(--device-artwork-server-led-opacity);
}

.device-status-artwork__server-button {
  position: absolute;
  bottom: var(--device-artwork-server-button-bottom);
  left: var(--device-artwork-server-button-left);
  width: var(--device-artwork-server-button-size);
  height: var(--device-artwork-server-button-size);
  border: var(--device-artwork-server-button-border-width) solid
    var(--device-artwork-server-button);
  border-radius: 50%;
}

.device-status-artwork__screen-glow,
.device-status-artwork__screen-shine,
.device-status-artwork__offline-mark,
.device-status-artwork__corner,
.device-status-artwork__pulse-ring {
  position: absolute;
  pointer-events: none;
}

.device-status-artwork__screen-glow {
  inset: 0;
  opacity: 0;
}

.device-status-artwork__screen-shine {
  top: -20%;
  left: -50%;
  width: 40%;
  height: 140%;
  opacity: 0;
  transform: skewX(-25deg);
}

.device-status-artwork__offline-mark {
  top: 50%;
  left: 50%;
  width: var(--device-artwork-offline-mark-size);
  height: var(--device-artwork-offline-mark-size);
  border-radius: 50%;
  opacity: 0;
  transform: translate(-50%, -50%);
}

.device-status-artwork__offline-mark::before {
  position: absolute;
  top: 50%;
  left: 50%;
  width: var(--device-artwork-offline-line-width);
  height: var(--device-artwork-offline-line-height);
  background: var(--device-artwork-offline-mark-color);
  border-radius: var(--device-artwork-offline-line-height);
  content: '';
  transform: translate(-50%, -50%);
}

.device-status-artwork__corner {
  top: var(--device-artwork-corner-top);
  right: var(--device-artwork-corner-right);
  width: var(--device-artwork-corner-size);
  height: var(--device-artwork-corner-size);
  border-radius: 50%;
  opacity: 0;
}

.device-status-artwork__pulse-ring {
  top: var(--device-artwork-pulse-top);
  right: var(--device-artwork-pulse-right);
  width: var(--device-artwork-pulse-size);
  height: var(--device-artwork-pulse-size);
  border: var(--device-artwork-pulse-border-width) solid transparent;
  border-radius: 50%;
  opacity: 0;
}

.device-status-artwork--online .device-status-artwork__screen {
  background: var(--device-artwork-screen-online);
}

.device-status-artwork--online .device-status-artwork__screen-glow {
  background: var(--device-artwork-screen-glow);
  opacity: 1;
}

.device-status-artwork--online .device-status-artwork__corner {
  background: var(--device-artwork-online);
  box-shadow: var(--device-artwork-online-corner-shadow);
  opacity: 1;
}

.device-status-artwork--online .device-status-artwork__pulse-ring {
  border-color: var(--device-artwork-online-ring);
  opacity: 1;
  animation: device-online-pulse var(--device-artwork-online-duration) ease-out
    infinite;
}

.device-status-artwork--online .device-status-artwork__server {
  background: var(--device-artwork-server-online);
}

.device-status-artwork--online .device-status-artwork__server-leds i {
  background: var(--device-artwork-server-led-online);
  box-shadow: var(--device-artwork-server-led-online-shadow);
}

.device-status-artwork--running .device-status-artwork__screen {
  background: var(--device-artwork-screen-running);
}

.device-status-artwork--running .device-status-artwork__screen-shine {
  background: var(--device-artwork-screen-shine);
  opacity: 1;
  animation: device-running-shine var(--device-artwork-running-duration) linear
    infinite;
}

.device-status-artwork--running .device-status-artwork__corner {
  background: var(--device-artwork-running);
  box-shadow: var(--device-artwork-running-corner-shadow);
  opacity: 1;
}

.device-status-artwork--running .device-status-artwork__server {
  background: var(--device-artwork-server-running);
}

.device-status-artwork--running .device-status-artwork__server-leds i {
  background: var(--device-artwork-server-led-running);
  box-shadow: var(--device-artwork-server-led-running-shadow);
  animation: device-running-led var(--device-artwork-running-led-duration)
    ease-in-out infinite;
}

.device-status-artwork--offline .device-status-artwork__desktop,
.device-status-artwork--offline .device-status-artwork__laptop,
.device-status-artwork--offline .device-status-artwork__server {
  filter: var(--device-artwork-offline-filter);
}

.device-status-artwork--offline .device-status-artwork__screen {
  background: var(--device-artwork-screen-offline);
}

.device-status-artwork--offline .device-status-artwork__offline-mark {
  border: var(--device-artwork-offline-mark-border-width) solid
    var(--device-artwork-offline-mark-color);
  opacity: 1;
}

.device-status-artwork--offline .device-status-artwork__server {
  background: var(--device-artwork-server-offline);
}

.device-status-artwork--offline .device-status-artwork__server-leds i {
  background: var(--device-artwork-server-led-offline);
}

@keyframes device-online-pulse {
  0% {
    opacity: 0.75;
    transform: scale(0.72);
  }
  70%,
  100% {
    opacity: 0;
    transform: scale(1.25);
  }
}

@keyframes device-running-shine {
  0% {
    left: -50%;
    opacity: 0;
  }
  15% {
    opacity: 0.9;
  }
  55% {
    opacity: 0.45;
  }
  100% {
    left: 120%;
    opacity: 0;
  }
}

@keyframes device-running-led {
  0%,
  100% {
    opacity: 0.55;
  }
  50% {
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .device-status-artwork__pulse-ring,
  .device-status-artwork__screen-shine,
  .device-status-artwork__server-leds i {
    animation: none;
  }
}
</style>
