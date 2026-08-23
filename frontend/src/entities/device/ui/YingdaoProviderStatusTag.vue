<script setup lang="ts">
import { computed } from 'vue'

import StatusTag from '@/shared/components/StatusTag.vue'

import { YINGDAO_PROVIDER_STATUS_META } from '../model/status-meta'
import type { YingdaoProviderStatus } from '../model/types'

const props = defineProps<{ status: YingdaoProviderStatus }>()
const meta = computed(() => YINGDAO_PROVIDER_STATUS_META[props.status])
</script>

<template>
  <StatusTag :label="meta.label" :tone="meta.tone" />
</template>
