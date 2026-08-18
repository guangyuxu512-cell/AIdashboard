<script setup lang="ts">
import { computed } from 'vue'

import StatusTag from '@/shared/components/StatusTag.vue'

import { YINGDAO_AVAILABILITY_META } from '../model/status-meta'
import type { YingdaoAvailabilityStatus } from '../model/types'

const props = defineProps<{ status: YingdaoAvailabilityStatus }>()
const meta = computed(() => YINGDAO_AVAILABILITY_META[props.status])
</script>

<template>
  <StatusTag :label="meta.label" :tone="meta.tone" />
</template>
