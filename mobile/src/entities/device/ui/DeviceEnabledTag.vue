<script setup lang="ts">
import { Tag as VanTag } from 'vant'
import { computed } from 'vue'

import { DEVICE_ENABLED_META } from '../model/device-meta'

const props = defineProps<{ enabled: boolean }>()

const meta = computed(
  () => DEVICE_ENABLED_META[props.enabled ? 'enabled' : 'disabled'],
)
</script>

<template>
  <VanTag :type="meta.tagType" round>{{ meta.label }}</VanTag>
</template>
