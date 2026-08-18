<script setup lang="ts">
import { NDrawer, NDrawerContent } from 'naive-ui'

import type { OverlaySize } from './types'

const drawerWidths: Record<OverlaySize, string> = {
  sm: 'var(--drawer-width-sm)',
  md: 'var(--drawer-width-md)',
  lg: 'var(--drawer-width-lg)',
}

withDefaults(
  defineProps<{
    show: boolean
    title: string
    size?: OverlaySize
    closable?: boolean
  }>(),
  {
    size: 'md',
    closable: true,
  },
)

defineEmits<{
  'update:show': [value: boolean]
}>()
</script>

<template>
  <NDrawer
    :show="show"
    :width="drawerWidths[size]"
    :mask-closable="false"
    @update:show="$emit('update:show', $event)"
  >
    <NDrawerContent :title="title" :closable="closable">
      <slot />
      <template v-if="$slots.footer" #footer>
        <slot name="footer" />
      </template>
    </NDrawerContent>
  </NDrawer>
</template>
