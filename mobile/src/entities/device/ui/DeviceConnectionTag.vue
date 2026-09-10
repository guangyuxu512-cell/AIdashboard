<script setup lang="ts">
import { Tag as VanTag } from 'vant'
import { computed } from 'vue'

import type { DeviceConnectionStatusDto } from '../api/contracts'
import {
  DEVICE_CONNECTION_DISPLAY_META,
  getDeviceConnectionDisplayState,
} from '../model/device-meta'

const props = defineProps<{
  status: DeviceConnectionStatusDto | null | undefined
}>()

const meta = computed(
  () =>
    DEVICE_CONNECTION_DISPLAY_META[
      getDeviceConnectionDisplayState(props.status)
    ],
)
</script>

<template>
  <VanTag :type="meta.tagType" round>{{ meta.label }}</VanTag>
</template>
