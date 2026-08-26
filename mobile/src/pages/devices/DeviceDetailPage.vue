<script setup lang="ts">
import {
  Button as VanButton,
  Cell as VanCell,
  CellGroup as VanCellGroup,
  Collapse as VanCollapse,
  CollapseItem as VanCollapseItem,
  Empty as VanEmpty,
  Skeleton as VanSkeleton,
} from 'vant'
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { MOBILE_ROUTE_NAMES } from '@/app/router/routes'
import {
  DeviceConnectionTag,
  DeviceEnabledTag,
  formatDeviceDateTime,
  formatRelativeHeartbeat,
} from '@/entities/device'
import {
  ActiveTaskSummary,
  DeviceProviderDetails,
  DeviceProviderSection,
  DeviceSkillDetails,
  DeviceSkillSummary,
  useDeviceDetail,
} from '@/features/device-center'
import { AppPage } from '@/shared/ui'

const route = useRoute()
const router = useRouter()
const deviceId = computed(() => String(route.params.deviceId ?? ''))
const detail = useDeviceDetail(deviceId)
const expanded = ref<string[]>([])

function openTask(taskId: string): void {
  void router.push({
    name: MOBILE_ROUTE_NAMES.taskDetail,
    params: { taskId },
    query: { fromDeviceId: deviceId.value },
  })
}
</script>

<template>
  <AppPage class="device-detail-page">
    <div
      v-if="detail.isDeviceInitialLoading.value"
      data-testid="device-detail-loading"
    >
      <VanSkeleton title :row="8" />
    </div>

    <VanEmpty
      v-else-if="detail.isDeviceInitialError.value || !detail.device.value"
      image="error"
      description="加载失败"
      data-testid="device-detail-error"
    >
      <VanButton type="primary" @click="detail.deviceQuery.refetch()">
        重试
      </VanButton>
    </VanEmpty>

    <template v-else>
      <section class="device-detail-page__summary" data-testid="device-detail">
        <div class="device-detail-page__title">
          <h1>{{ detail.device.value.displayName }}</h1>
          <div class="device-detail-page__tags">
            <DeviceEnabledTag :enabled="detail.device.value.enabled" />
            <DeviceConnectionTag
              :status="detail.device.value.workerRuntime?.connectionStatus"
            />
          </div>
        </div>
      </section>

      <ActiveTaskSummary
        class="device-detail-page__current-task"
        :task="detail.activeTask.query.data.value"
        :initial-loading="detail.activeTask.isInitialLoading.value"
        :initial-error="detail.activeTask.isInitialError.value"
        @retry="detail.activeTask.query.refetch"
        @select="openTask"
      />

      <section
        class="device-detail-page__runtime"
        aria-labelledby="runtime-title"
      >
        <h2 id="runtime-title">运行端</h2>
        <VanEmpty
          v-if="!detail.device.value.workerRuntime"
          description="未上报"
          data-testid="runtime-unreported"
        />
        <VanCellGroup v-else>
          <VanCell
            title="Worker"
            :value="detail.device.value.workerRuntime.workerVersion"
          />
          <VanCell
            title="心跳"
            :value="
              formatRelativeHeartbeat(
                detail.device.value.workerRuntime.lastSeenAt,
              )
            "
          />
        </VanCellGroup>
      </section>

      <DeviceProviderSection
        :inventories="detail.provider.query.data.value"
        :initial-loading="detail.provider.isInitialLoading.value"
        :initial-error="detail.provider.isInitialError.value"
        @retry="detail.provider.query.refetch"
      />

      <DeviceSkillSummary
        :capabilities="detail.capability.query.data.value"
        :initial-loading="detail.capability.isInitialLoading.value"
        :initial-error="detail.capability.isInitialError.value"
        @retry="detail.capability.query.refetch"
      />

      <VanCollapse v-model="expanded" data-testid="device-more-information">
        <VanCollapseItem title="更多信息" name="device-details">
          <div class="device-detail-page__details">
            <section>
              <h3>设备技术信息</h3>
              <VanCellGroup>
                <VanCell
                  title="设备 ID"
                  :value="detail.device.value.deviceId"
                />
                <VanCell
                  title="位置"
                  :value="detail.device.value.location || '—'"
                />
                <VanCell
                  title="备注"
                  :value="detail.device.value.note || '—'"
                />
              </VanCellGroup>
            </section>

            <section v-if="detail.device.value.workerRuntime">
              <h3>运行端技术信息</h3>
              <VanCellGroup>
                <VanCell
                  title="运行端启动时间"
                  :value="
                    formatDeviceDateTime(
                      detail.device.value.workerRuntime.startedAt,
                    )
                  "
                />
                <VanCell
                  title="运行端更新时间"
                  :value="
                    formatDeviceDateTime(
                      detail.device.value.workerRuntime.updatedAt,
                    )
                  "
                />
              </VanCellGroup>
            </section>

            <DeviceProviderDetails
              v-if="detail.provider.query.data.value !== undefined"
              :inventories="detail.provider.query.data.value"
            />
            <DeviceSkillDetails
              v-if="detail.capability.query.data.value !== undefined"
              :capabilities="detail.capability.query.data.value"
            />
          </div>
        </VanCollapseItem>
      </VanCollapse>
    </template>
  </AppPage>
</template>

<style scoped>
.device-detail-page {
  padding-bottom: var(--space-6);
}

.device-detail-page__summary,
.device-detail-page__runtime {
  display: grid;
  min-width: 0;
  gap: var(--space-3);
}

.device-detail-page__current-task,
.device-detail-page__runtime {
  padding: var(--space-3);
  background: var(--bg-surface);
  border: var(--border-width) solid var(--border-subtle);
  border-radius: var(--radius-card);
}

.device-detail-page__title,
.device-detail-page__tags {
  display: flex;
  min-width: 0;
  gap: var(--space-2);
  align-items: flex-start;
  justify-content: space-between;
}

.device-detail-page__title h1 {
  min-width: 0;
  overflow-wrap: anywhere;
  font-size: var(--font-size-title);
  line-height: var(--line-height-title);
}

.device-detail-page__tags {
  flex: none;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.device-detail-page__runtime h2 {
  font-size: var(--font-size-label);
  line-height: var(--line-height-label);
}

.device-detail-page__details {
  display: grid;
  gap: var(--space-4);
}

.device-detail-page__details section {
  display: grid;
  min-width: 0;
  gap: var(--space-2);
}

.device-detail-page__details h3 {
  font-size: var(--font-size-label);
  line-height: var(--line-height-label);
}
</style>
