<script setup lang="ts">
import { NDescriptions, NDescriptionsItem } from 'naive-ui'

import {
  DEVICE_CAPABILITY_AVAILABILITY_META,
  DEVICE_CAPABILITY_META,
  DeviceStatusTag,
  type DeviceListItemViewModel,
} from '@/entities/device'
import DetailDrawer from '@/shared/components/DetailDrawer.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import AppButton from '@/shared/ui/AppButton.vue'

defineProps<{ show: boolean; device: DeviceListItemViewModel | null }>()

defineEmits<{ 'update:show': [value: boolean] }>()
</script>

<template>
  <DetailDrawer
    :show="show"
    title="设备详情"
    size="md"
    @update:show="$emit('update:show', $event)"
  >
    <div v-if="device" class="device-detail">
      <section>
        <h3>基础信息</h3>
        <NDescriptions :column="1" label-placement="left" bordered>
          <NDescriptionsItem label="设备名称">{{
            device.deviceName
          }}</NDescriptionsItem>
          <NDescriptionsItem label="位置">{{
            device.location
          }}</NDescriptionsItem>
          <NDescriptionsItem label="标签">{{
            device.tags.join('、')
          }}</NDescriptionsItem>
          <NDescriptionsItem label="系统">{{
            device.systemDisplay
          }}</NDescriptionsItem>
          <NDescriptionsItem label="Worker 版本">
            {{ device.workerVersionDisplay }}
          </NDescriptionsItem>
        </NDescriptions>
      </section>

      <section>
        <h3>运行状态</h3>
        <NDescriptions :column="1" label-placement="left" bordered>
          <NDescriptionsItem label="设备状态">
            <DeviceStatusTag :status="device.status" />
          </NDescriptionsItem>
          <NDescriptionsItem label="当前任务">
            {{ device.currentTaskName ?? '无运行中任务' }}
          </NDescriptionsItem>
          <NDescriptionsItem label="最近心跳">
            {{ device.lastHeartbeatAtDisplay }}
          </NDescriptionsItem>
          <NDescriptionsItem label="CPU 摘要">{{
            device.cpuUsageDisplay
          }}</NDescriptionsItem>
          <NDescriptionsItem label="内存摘要">
            {{ device.memoryUsageDisplay }}
          </NDescriptionsItem>
        </NDescriptions>
      </section>

      <section>
        <h3>执行能力</h3>
        <ul class="device-detail__capabilities">
          <li
            v-for="capability in device.capabilities"
            :key="capability.capability"
          >
            <span>{{
              DEVICE_CAPABILITY_META[capability.capability].label
            }}</span>
            <StatusTag
              :label="
                DEVICE_CAPABILITY_AVAILABILITY_META[capability.availability]
                  .label
              "
              :tone="
                DEVICE_CAPABILITY_AVAILABILITY_META[capability.availability]
                  .tone
              "
            />
          </li>
        </ul>
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

.device-detail__capabilities {
  display: grid;
  margin: 0;
  padding: 0;
  gap: var(--space-3);
  grid-template-columns: repeat(2, minmax(0, 1fr));
  list-style: none;
}

.device-detail__capabilities li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--color-border-default);
  border-radius: var(--radius-card);
  background: var(--color-bg-subtle);
}
</style>
