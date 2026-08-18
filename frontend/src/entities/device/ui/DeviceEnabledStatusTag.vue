<script setup lang="ts">
import { computed } from 'vue'

import StatusTag from '@/shared/components/StatusTag.vue'

import { DEVICE_ENABLED_STATUS_META } from '../model/status-meta'
import type { DeviceEnabledStatus } from '../model/types'

const props = defineProps<{ status: DeviceEnabledStatus }>()
const meta = computed(() => DEVICE_ENABLED_STATUS_META[props.status])
</script>

<template>
  <StatusTag :label="meta.label" :tone="meta.tone" />
</template>
