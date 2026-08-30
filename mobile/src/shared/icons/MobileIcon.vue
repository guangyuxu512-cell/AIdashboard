<script setup lang="ts">
import { Icon as VanIcon } from 'vant'
import { computed } from 'vue'

import {
  resolveMobileIcon,
  type MobileIconName,
  type MobileIconTone,
} from './icon-registry'

const props = withDefaults(
  defineProps<{
    name: MobileIconName | string
    size?: number | string
    tone?: MobileIconTone
    decorative?: boolean
    label?: string
    tile?: boolean
  }>(),
  {
    decorative: true,
    label: undefined,
    size: undefined,
    tone: undefined,
    tile: false,
  },
)

const definition = computed(() => resolveMobileIcon(props.name))
const resolvedTone = computed(() => props.tone ?? definition.value.tone)
const isDecorative = computed(() => props.decorative && !props.label)
const iconStyle = computed(() => {
  if (props.size === undefined) return undefined
  return {
    fontSize: typeof props.size === 'number' ? `${props.size}px` : props.size,
  }
})
</script>

<template>
  <span
    class="mobile-icon"
    :class="[
      `mobile-icon--${definition.role}`,
      resolvedTone ? `mobile-icon--tone-${resolvedTone}` : undefined,
      { 'mobile-icon--tile': tile },
    ]"
    :style="iconStyle"
    :data-icon-key="name"
    :data-icon-role="definition.role"
    :aria-hidden="isDecorative ? 'true' : undefined"
    :aria-label="label"
    :role="label ? 'img' : undefined"
  >
    <VanIcon
      v-if="definition.source.kind === 'vant'"
      class="mobile-icon__vant"
      :name="definition.source.name"
    />
    <component
      :is="definition.source.component"
      v-else-if="definition.source.kind === 'component'"
    />
    <img
      v-else
      class="mobile-icon__asset"
      :src="definition.source.src"
      alt=""
    />
  </span>
</template>

<style scoped>
.mobile-icon {
  display: inline-grid;
  width: 1em;
  height: 1em;
  flex: none;
  color: inherit;
  font-size: inherit;
  line-height: 1;
  place-items: center;
}

.mobile-icon__vant,
.mobile-icon__asset,
.mobile-icon :deep(.mobile-icon__glyph) {
  display: block;
  width: 100%;
  height: 100%;
  font-size: inherit;
  line-height: 1;
}

.mobile-icon__asset {
  object-fit: contain;
}

.mobile-icon--tone-primary {
  color: var(--color-primary);
}

.mobile-icon--tone-success {
  color: var(--status-success);
}

.mobile-icon--tone-warning {
  color: var(--status-warning);
}

.mobile-icon--tone-danger {
  color: var(--status-danger);
}

.mobile-icon--tone-muted {
  color: var(--text-muted);
}

.mobile-icon--tone-secondary {
  color: var(--text-secondary);
}

.mobile-icon--tile {
  width: var(--icon-size-card-leading);
  height: var(--icon-size-card-leading);
  color: var(--color-primary);
  background: var(--color-primary-soft);
  border: var(--border-width) solid transparent;
  border-radius: var(--radius-control);
  box-shadow: var(--appearance-border-control);
}
</style>
