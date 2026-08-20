<script setup lang="ts">
import { computed } from 'vue'

import type { ResolvedTheme } from '@/stores/theme'

import { officeThemeLayerAssets } from '../assets/office-2d-asset-manifest'

const props = defineProps<{ resolvedTheme: ResolvedTheme }>()
const source = computed(() => officeThemeLayerAssets[props.resolvedTheme].foreground)
</script>

<template>
  <div class="office-stage-layer office-foreground-layer" aria-hidden="true">
    <img :src="source" alt="" draggable="false" />
  </div>
</template>
