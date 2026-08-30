<script setup lang="ts">
import { Cell as VanCell, CellGroup as VanCellGroup } from 'vant'

import {
  formatDeviceDateTime,
  type DeviceProviderInventoryReadDto,
} from '@/entities/device'

defineProps<{
  inventories: DeviceProviderInventoryReadDto[] | undefined
}>()

function booleanText(value: boolean | null): string {
  if (value === null) return '—'
  return value ? '是' : '否'
}
</script>

<template>
  <section class="device-provider-details" aria-label="提供方技术信息">
    <h3>提供方技术信息</h3>
    <p v-if="!inventories?.length" class="device-provider-details__empty">
      暂无信息
    </p>
    <VanCellGroup
      v-for="item in inventories"
      v-else
      :key="item.provider_code"
      data-testid="provider-technical-details"
    >
      <VanCell title="提供方代码" :value="item.provider_code" />
      <VanCell
        title="提供方可用"
        :value="booleanText(item.inventory.available)"
      />
      <VanCell
        title="执行接口可用"
        :value="booleanText(item.inventory.execution_available)"
      />
      <VanCell title="已登录" :value="booleanText(item.inventory.logged_in)" />
      <VanCell title="账号类型" :value="item.account_type || '—'" />
      <VanCell title="企业账号" :value="booleanText(item.enterprise_account)" />
      <VanCell
        title="执行接口版本"
        :value="item.inventory.execution_version || '—'"
      />
      <VanCell
        title="发现时间"
        :value="formatDeviceDateTime(item.last_discovered_at)"
      />
      <VanCell v-if="item.inventory.status_reason" title="状态说明">
        <template #value>
          <span class="device-provider-details__long-value">
            {{ item.inventory.status_reason }}
          </span>
        </template>
      </VanCell>
      <VanCell
        v-if="item.inventory.execution_unavailable_reason"
        title="执行不可用说明"
      >
        <template #value>
          <span class="device-provider-details__long-value">
            {{ item.inventory.execution_unavailable_reason }}
          </span>
        </template>
      </VanCell>
    </VanCellGroup>
  </section>
</template>

<style scoped>
.device-provider-details {
  display: grid;
  min-width: 0;
  gap: var(--layout-content-gap);
}

.device-provider-details h3 {
  font-size: var(--font-size-label);
  line-height: var(--line-height-label);
}

.device-provider-details__empty {
  color: var(--text-secondary);
}

.device-provider-details__long-value {
  min-width: 0;
  overflow-wrap: anywhere;
  white-space: normal;
}
</style>
