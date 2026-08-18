<script setup lang="ts">
import StatusTag from '@/shared/components/StatusTag.vue'

import { SHOP_SESSION_STATUS_META } from '../model/status-meta'
import type { ShopSessionStatus } from '../model/types'

const props = defineProps<{ status: ShopSessionStatus }>()
</script>

<template>
  <StatusTag v-bind="SHOP_SESSION_STATUS_META[props.status]" />
</template>
