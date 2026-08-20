<script setup lang="ts">
import { NDescriptions, NDescriptionsItem } from 'naive-ui'

import {
  DeviceEnabledStatusTag,
  DeviceStatusTag,
  type DeviceListItemViewModel,
  type YingdaoInventoryViewModel,
  YingdaoAvailabilityStatusTag,
} from '@/entities/device'
import DetailDrawer from '@/shared/components/DetailDrawer.vue'
import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import AppButton from '@/shared/ui/AppButton.vue'

defineProps<{
  show: boolean
  device: DeviceListItemViewModel | null
  loading?: boolean
  error?: string | null
  yingdaoInventory?: YingdaoInventoryViewModel | null
  providerInventoryLoading?: boolean
  providerInventoryError?: string | null
  yingdaoRefreshing?: boolean
}>()

defineEmits<{
  'update:show': [value: boolean]
  retry: []
  'retry-provider-inventory': []
  'refresh-yingdao': []
  'view-yingdao-applications': []
}>()
</script>

<template>
  <DetailDrawer
    :show="show"
    title="设备详情"
    size="md"
    @update:show="$emit('update:show', $event)"
  >
    <LoadingState v-if="loading" description="正在加载设备详情…" />
    <ErrorState
      v-else-if="error"
      :description="error"
      retryable
      @retry="$emit('retry')"
    />
    <div v-else-if="device" class="device-detail">
      <section>
        <h3>基础信息</h3>
        <NDescriptions :column="1" label-placement="left" bordered>
          <NDescriptionsItem label="设备名称">{{
            device.deviceName
          }}</NDescriptionsItem>
          <NDescriptionsItem label="Device ID">{{
            device.deviceId
          }}</NDescriptionsItem>
          <NDescriptionsItem label="位置">{{
            device.location
          }}</NDescriptionsItem>
          <NDescriptionsItem label="启用状态">
            <DeviceEnabledStatusTag :status="device.enabledStatus" />
          </NDescriptionsItem>
        </NDescriptions>
      </section>

      <section>
        <h3>Worker</h3>
        <NDescriptions :column="1" label-placement="left" bordered>
          <NDescriptionsItem label="连接状态">
            <DeviceStatusTag :status="device.runtimeStatus" />
          </NDescriptionsItem>
          <NDescriptionsItem label="Worker 版本">
            {{ device.workerVersionDisplay }}
          </NDescriptionsItem>
          <NDescriptionsItem label="最近心跳">
            {{ device.lastHeartbeatAtDisplay }}
          </NDescriptionsItem>
        </NDescriptions>
      </section>

      <section>
        <div class="device-detail__section-heading">
          <h3>影刀环境</h3>
          <div class="device-detail__section-actions">
            <AppButton
              v-if="yingdaoInventory?.applicationCount"
              tone="text"
              @click="$emit('view-yingdao-applications')"
            >
              查看已同步应用
            </AppButton>
            <AppButton
              :loading="yingdaoRefreshing"
              :disabled="device.dataSource !== 'real'"
              @click="$emit('refresh-yingdao')"
            >
              刷新影刀能力
            </AppButton>
          </div>
        </div>
        <LoadingState
          v-if="providerInventoryLoading"
          description="正在读取影刀环境…"
        />
        <ErrorState
          v-else-if="providerInventoryError"
          :description="providerInventoryError"
          retryable
          @retry="$emit('retry-provider-inventory')"
        />
        <NDescriptions v-else :column="1" label-placement="left" bordered>
          <NDescriptionsItem label="影刀">
            <YingdaoAvailabilityStatusTag
              :status="
                yingdaoInventory
                  ? yingdaoInventory.availabilityStatus
                  : 'not_detected'
              "
            />
          </NDescriptionsItem>
          <NDescriptionsItem label="版本">
            {{ yingdaoInventory?.providerVersion ?? '未检测' }}
          </NDescriptionsItem>
          <NDescriptionsItem label="账号">
            {{ yingdaoInventory?.accountDisplay ?? '未检测' }}
          </NDescriptionsItem>
          <NDescriptionsItem label="账号类型">
            {{ yingdaoInventory?.accountType ?? '未检测' }}
          </NDescriptionsItem>
          <NDescriptionsItem label="本机已同步应用">
            {{ yingdaoInventory?.applicationCount ?? 0 }}
          </NDescriptionsItem>
          <NDescriptionsItem label="最近检测">
            {{ yingdaoInventory?.lastDiscoveredAtDisplay ?? '尚未检测' }}
          </NDescriptionsItem>
        </NDescriptions>
      </section>

      <section>
        <h3>执行关系</h3>
        <NDescriptions :column="1" label-placement="left" bordered>
          <NDescriptionsItem label="绑定店铺">
            <StatusTag label="待接入" tone="neutral" />
          </NDescriptionsItem>
        </NDescriptions>
      </section>
    </div>

    <template #footer>
      <AppButton @click="$emit('update:show', false)">关闭</AppButton>
    </template>
  </DetailDrawer>
</template>

<style scoped>
.device-detail {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.device-detail section {
  min-width: 0;
}

.device-detail h3 {
  margin-bottom: var(--space-3);
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
}

.device-detail__section-heading,
.device-detail__section-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.device-detail__section-heading h3 {
  margin-bottom: 0;
}
</style>
