<script setup lang="ts">
import { computed } from 'vue'

import StatusTag from '@/shared/components/StatusTag.vue'

import { SHOP_ENABLED_STATUS_META } from '../model/status-meta'
import type { ShopEnabledStatus } from '../model/types'

const props = defineProps<{ status: ShopEnabledStatus }>()

const meta = computed(() => SHOP_ENABLED_STATUS_META[props.status])
</script>

<template>
  <StatusTag :label="meta.label" :tone="meta.tone" />
</template>
