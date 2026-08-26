<script setup lang="ts">
import {
  Button as VanButton,
  Cell as VanCell,
  CellGroup as VanCellGroup,
  Empty as VanEmpty,
  Loading as VanLoading,
  NoticeBar as VanNoticeBar,
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
  backgroundError: boolean
  errorMessage: string
}>()

const emit = defineEmits<{ retry: [] }>()
</script>

<template>
  <section class="device-provider-section" aria-labelledby="provider-title">
    <h2 id="provider-title">影刀提供方</h2>
    <div v-if="backgroundError" class="device-provider-section__error">
      <VanNoticeBar
        type="warning"
        :text="`${errorMessage}，已保留上次影刀快照`"
        wrapable
      />
      <VanButton block @click="emit('retry')">重新加载影刀快照</VanButton>
    </div>

    <div v-if="initialLoading" class="device-provider-section__state">
      <VanLoading>加载影刀快照中</VanLoading>
    </div>
    <VanEmpty
      v-else-if="initialError"
      image="error"
      :description="errorMessage"
    >
      <VanButton type="primary" @click="emit('retry')">重新加载</VanButton>
    </VanEmpty>
    <VanEmpty
      v-else-if="inventories?.length === 0"
      description="尚未上报影刀快照"
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
        <VanCell
          title="提供方版本"
          :value="item.inventory.provider_version || '—'"
        />
        <VanCell
          title="影刀应用数"
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
}

.device-provider-section h2 {
  font-size: var(--font-size-label);
  line-height: var(--line-height-label);
}

.device-provider-section__state {
  display: grid;
  min-height: 96px;
  place-items: center;
}

.device-provider-section__error {
  display: grid;
  gap: var(--space-2);
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
