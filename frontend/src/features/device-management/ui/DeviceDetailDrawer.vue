<script setup lang="ts">
import { NCollapse, NCollapseItem } from 'naive-ui'

import {
  DeviceConnectionStatusTag,
  DeviceEnabledStatusTag,
  DeviceIdentity,
  type DeviceListItemViewModel,
  type YingdaoInventoryViewModel,
  YingdaoAvailabilityStatusTag,
} from '@/entities/device'
import DetailDrawer from '@/shared/components/DetailDrawer.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import AppButton from '@/shared/ui/AppButton.vue'

import type {
  DeviceCurrentExecutionViewModel,
  DeviceRecentExecutionViewModel,
} from '../model/types'
import DeviceCapabilityCard from './DeviceCapabilityCard.vue'

defineProps<{
  show: boolean
  device: DeviceListItemViewModel | null
  loading?: boolean
  error?: string | null
  yingdaoInventory?: YingdaoInventoryViewModel | null
  providerInventoryLoading?: boolean
  providerInventoryError?: string | null
  yingdaoRefreshing?: boolean
  currentExecution?: DeviceCurrentExecutionViewModel | null
  boundShopCount?: number | null
  recentExecutions?: DeviceRecentExecutionViewModel[]
  statusChanging?: boolean
  removing?: boolean
}>()

defineEmits<{
  'update:show': [value: boolean]
  retry: []
  'retry-provider-inventory': []
  'refresh-yingdao': []
  'view-yingdao-applications': []
  edit: [device: DeviceListItemViewModel]
  'toggle-enabled': [device: DeviceListItemViewModel]
  remove: [device: DeviceListItemViewModel]
}>()
</script>

<template>
  <DetailDrawer
    :show="show"
    title="设备详情"
    size="md"
    @update:show="$emit('update:show', $event)"
  >
    <template v-if="device" #header>
      <div class="device-detail-header">
        <DeviceIdentity :name="device.deviceName" />
        <div class="device-detail-header__statuses">
          <DeviceConnectionStatusTag :status="device.runtimeStatus" />
          <DeviceEnabledStatusTag :status="device.enabledStatus" />
        </div>
      </div>
    </template>

    <LoadingState v-if="loading" description="正在加载设备详情…" />
    <ErrorState
      v-else-if="error"
      :description="error"
      retryable
      @retry="$emit('retry')"
    />
    <div v-else-if="device" class="device-detail">
      <section class="device-detail__section">
        <h3>运行概览</h3>
        <div class="device-overview">
          <div class="device-overview__item">
            <span>当前状态</span>
            <StatusTag
              :label="currentExecution?.label ?? '—'"
              :tone="currentExecution?.tone ?? 'neutral'"
            />
          </div>
          <div class="device-overview__item">
            <span>当前执行</span>
            <strong>{{ currentExecution?.name ?? '—' }}</strong>
          </div>
          <div class="device-overview__item">
            <span>最后心跳</span>
            <strong>{{ device.lastHeartbeatAtDisplay }}</strong>
          </div>
          <div class="device-overview__item">
            <span>绑定店铺</span>
            <strong>{{ boundShopCount ?? '—' }}</strong>
          </div>
        </div>
      </section>

      <section class="device-detail__section">
        <h3>执行能力</h3>
        <DeviceCapabilityCard
          title="影刀 RPA"
          description="本机影刀环境与已同步应用"
        >
          <template #status>
            <YingdaoAvailabilityStatusTag
              :status="yingdaoInventory?.availabilityStatus ?? 'not_detected'"
            />
          </template>

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
          <dl v-else class="capability-facts">
            <div>
              <dt>账号</dt>
              <dd>{{ yingdaoInventory?.accountDisplay ?? '—' }}</dd>
            </div>
            <div>
              <dt>账号类型</dt>
              <dd>{{ yingdaoInventory?.accountType ?? '—' }}</dd>
            </div>
            <div>
              <dt>本机已同步应用</dt>
              <dd>{{ yingdaoInventory?.applicationCount ?? '—' }}</dd>
            </div>
            <div>
              <dt>版本</dt>
              <dd>{{ yingdaoInventory?.providerVersion ?? '—' }}</dd>
            </div>
          </dl>

          <template #actions>
            <AppButton
              tone="text"
              :disabled="!yingdaoInventory?.applicationCount"
              @click="$emit('view-yingdao-applications')"
            >
              查看应用
            </AppButton>
            <AppButton
              :loading="yingdaoRefreshing"
              :disabled="device.dataSource !== 'real'"
              @click="$emit('refresh-yingdao')"
            >
              刷新影刀能力
            </AppButton>
          </template>
        </DeviceCapabilityCard>
      </section>

      <section class="device-detail__section">
        <h3>最近执行</h3>
        <ul v-if="recentExecutions?.length" class="recent-executions">
          <li v-for="execution in recentExecutions" :key="execution.id">
            <strong>{{ execution.name }}</strong>
            <StatusTag :label="execution.statusLabel" :tone="execution.tone" />
            <span>{{ execution.timeDisplay }}</span>
          </li>
        </ul>
        <EmptyState v-else description="暂无可用的最近执行记录" />
      </section>

      <section class="device-detail__section device-detail__section--muted">
        <NCollapse>
          <NCollapseItem title="更多信息" name="more-information">
            <dl class="more-information">
              <div>
                <dt>设备 ID</dt>
                <dd>{{ device.deviceId }}</dd>
              </div>
              <div>
                <dt>位置</dt>
                <dd>{{ device.location }}</dd>
              </div>
              <div>
                <dt>标签</dt>
                <dd>{{ device.tags.join('、') || '—' }}</dd>
              </div>
              <div>
                <dt>备注</dt>
                <dd>{{ device.note || '—' }}</dd>
              </div>
              <div>
                <dt>Worker 版本</dt>
                <dd>{{ device.workerVersionDisplay }}</dd>
              </div>
            </dl>
          </NCollapseItem>
        </NCollapse>
      </section>
    </div>

    <template #footer>
      <div v-if="device" class="device-detail-footer">
        <AppButton tone="danger" :loading="removing" @click="$emit('remove', device)">
          移除设备
        </AppButton>
        <span class="device-detail-footer__spacer" />
        <AppButton @click="$emit('edit', device)">编辑</AppButton>
        <AppButton
          :loading="statusChanging"
          @click="$emit('toggle-enabled', device)"
        >
          {{ device.enabled ? '停用设备' : '启用设备' }}
        </AppButton>
        <AppButton @click="$emit('update:show', false)">关闭</AppButton>
      </div>
    </template>
  </DetailDrawer>
</template>

<style scoped>
.device-detail-header {
  display: flex;
  min-width: 0;
  flex: 1;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.device-detail-footer {
  display: flex;
  width: 100%;
  align-items: center;
  gap: var(--space-2);
}

.device-detail-footer__spacer {
  flex: 1;
}

.device-detail-header :deep(.device-identity) {
  flex: 1;
  font-weight: var(--font-weight-semibold);
}

.device-detail-header__statuses {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: var(--space-2);
}

.device-detail {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-6);
}

.device-detail__section {
  min-width: 0;
}

.device-detail__section h3 {
  margin-bottom: var(--space-3);
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
}

.device-overview {
  display: grid;
  gap: var(--space-3);
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.device-overview__item {
  display: flex;
  min-width: 0;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  background: var(--bg-subtle);
}

.device-overview__item span,
.capability-facts dt,
.more-information dt,
.recent-executions span {
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.device-overview__item strong {
  max-width: 100%;
  overflow: hidden;
  font-weight: var(--font-weight-medium);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.capability-facts,
.more-information {
  display: grid;
  margin: 0;
  gap: var(--space-3) var(--space-5);
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.capability-facts div,
.more-information div {
  min-width: 0;
}

.capability-facts dd,
.more-information dd {
  margin: var(--space-1) 0 0;
  overflow-wrap: anywhere;
}

.recent-executions {
  display: flex;
  margin: 0;
  padding: 0;
  flex-direction: column;
  list-style: none;
}

.recent-executions li {
  display: grid;
  align-items: center;
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--border-subtle);
  gap: var(--space-3);
  grid-template-columns: minmax(0, 1fr) auto auto;
}

.device-detail__section--muted {
  color: var(--text-secondary);
}

@media (max-width: 720px) {
  .device-overview,
  .capability-facts,
  .more-information {
    grid-template-columns: 1fr;
  }
}
</style>
