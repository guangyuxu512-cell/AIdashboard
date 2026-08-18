<script setup lang="ts">
import { computed } from 'vue'

import StatusTag from '@/shared/components/StatusTag.vue'

import {
  SHOP_AUTOMATION_STATUS_META,
  SHOP_CONFIGURATION_STATUS_META,
  SHOP_OPERATIONAL_STATUS_META,
  SHOP_SESSION_STATUS_META,
} from '../model/status-meta'
import type {
  ShopAutomationStatus,
  ShopConfigurationStatus,
  ShopOperationalStatus,
  ShopSessionStatus,
} from '../model/types'

type ShopStatusTagProps =
  | { category: 'shop'; status: ShopOperationalStatus }
  | { category: 'session'; status: ShopSessionStatus }
  | { category: 'automation'; status: ShopAutomationStatus }
  | { category: 'configuration'; status: ShopConfigurationStatus }

const props = defineProps<ShopStatusTagProps>()

const meta = computed(() => {
  switch (props.category) {
    case 'shop':
      return SHOP_OPERATIONAL_STATUS_META[props.status]
    case 'session':
      return SHOP_SESSION_STATUS_META[props.status]
    case 'automation':
      return SHOP_AUTOMATION_STATUS_META[props.status]
    case 'configuration':
      return SHOP_CONFIGURATION_STATUS_META[props.status]
    default:
      throw new Error('未知店铺状态分类')
  }
})
</script>

<template>
  <StatusTag :label="meta.label" :tone="meta.tone" />
</template>
