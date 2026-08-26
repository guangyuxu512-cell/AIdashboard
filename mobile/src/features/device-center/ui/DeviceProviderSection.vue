<script setup lang="ts">
import {
  Button as VanButton,
  Cell as VanCell,
  CellGroup as VanCellGroup,
  Empty as VanEmpty,
  Loading as VanLoading,
  Tag as VanTag,
} from 'vant'

import {
  type DeviceProviderInventoryReadDto,
  YINGDAO_PROVIDER_STATUS_META,
} from '@/entities/device'

defineProps<{
  inventories: DeviceProviderInventoryReadDto[] | undefined
  initialLoading: boolean
  initialError: boolean
}>()

const emit = defineEmits<{ retry: [] }>()
</script>

<template>
  <section class="device-provider-section" aria-labelledby="provider-title">
    <h2 id="provider-title">影刀</h2>

    <div v-if="initialLoading" class="device-provider-section__state">
      <VanLoading>加载中</VanLoading>
    </div>
    <VanEmpty v-else-if="initialError" image="error" description="加载失败">
      <VanButton type="primary" @click="emit('retry')">重试</VanButton>
    </VanEmpty>
    <VanEmpty
      v-else-if="inventories?.length === 0"
      description="未上报"
      data-testid="provider-empty"
    />

    <article
      v-for="item in inventories"
      v-else
      :key="item.provider_code"
      class="device-provider-section__inventory"
      data-testid="provider-inventory"
    >
      <div class="device-provider-section__heading">
        <strong>影刀</strong>
        <VanTag
          :type="YINGDAO_PROVIDER_STATUS_META[item.inventory.status].tagType"
          round
        >
          {{ YINGDAO_PROVIDER_STATUS_META[item.inventory.status].label }}
        </VanTag>
      </div>

      <VanCellGroup data-testid="provider-primary-summary">
        <VanCell title="账号" :value="item.account_display || '—'" />
        <VanCell title="版本" :value="item.inventory.provider_version || '—'" />
        <VanCell
          title="应用"
          :value="`${item.inventory.applications.length} 个`"
        />
      </VanCellGroup>
    </article>
  </section>
</template>

<style scoped>
.device-provider-section {
  display: grid;
  min-width: 0;
  gap: var(--space-3);
  padding: var(--space-3);
  background: var(--bg-surface);
  border: var(--border-width) solid var(--border-subtle);
  border-radius: var(--radius-card);
}

.device-provider-section h2 {
  font-size: var(--font-size-label);
  line-height: var(--line-height-label);
}

.device-provider-section__state {
  display: grid;
  min-height: var(--layout-inline-state-min-height);
  place-items: center;
}

.device-provider-section__inventory {
  display: grid;
  min-width: 0;
  gap: var(--space-2);
}

.device-provider-section__heading {
  display: flex;
  gap: var(--space-2);
  align-items: center;
  justify-content: space-between;
}
</style>
