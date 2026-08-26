<script setup lang="ts">
import {
  Button as VanButton,
  Cell as VanCell,
  CellGroup as VanCellGroup,
  Collapse as VanCollapse,
  CollapseItem as VanCollapseItem,
  Empty as VanEmpty,
  NoticeBar as VanNoticeBar,
  Skeleton as VanSkeleton,
} from 'vant'
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { MOBILE_ROUTE_NAMES } from '@/app/router/routes'
import {
  DEVICE_CONNECTION_META,
  DeviceConnectionTag,
  DeviceEnabledTag,
  formatDeviceDateTime,
  formatRelativeHeartbeat,
} from '@/entities/device'
import {
  ActiveTaskSummary,
  DeviceProviderSection,
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
      :description="detail.deviceErrorMessage.value"
      data-testid="device-detail-error"
    >
      <VanButton type="primary" @click="detail.deviceQuery.refetch()">
        重新加载
      </VanButton>
    </VanEmpty>

    <template v-else>
      <VanNoticeBar
        v-if="detail.isDeviceBackgroundError.value"
        type="warning"
        :text="`${detail.deviceErrorMessage.value}，当前展示上次成功加载的数据`"
        wrapable
      />

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

        <ActiveTaskSummary
          :task="detail.activeTask.query.data.value"
          :initial-loading="detail.activeTask.isInitialLoading.value"
          :initial-error="detail.activeTask.isInitialError.value"
          :background-error="detail.activeTask.isBackgroundError.value"
          :error-message="detail.activeTask.errorMessage.value"
          @retry="detail.activeTask.query.refetch"
          @select="openTask"
        />
      </section>

      <section
        class="device-detail-page__runtime"
        aria-labelledby="runtime-title"
      >
        <h2 id="runtime-title">运行端信息</h2>
        <VanEmpty
          v-if="!detail.device.value.workerRuntime"
          description="未上报运行端信息"
          data-testid="runtime-unreported"
        />
        <VanCellGroup v-else inset>
          <VanCell
            title="连接状态"
            :value="
              DEVICE_CONNECTION_META[
                detail.device.value.workerRuntime.connectionStatus
              ].label
            "
          />
          <VanCell
            title="运行端版本"
            :value="detail.device.value.workerRuntime.workerVersion"
          />
          <VanCell
            title="最后心跳"
            :value="
              formatRelativeHeartbeat(
                detail.device.value.workerRuntime.lastSeenAt,
              )
            "
          />
          <VanCell
            title="运行端启动时间"
            :value="
              formatDeviceDateTime(detail.device.value.workerRuntime.startedAt)
            "
          />
          <VanCell
            title="运行端更新时间"
            :value="
              formatDeviceDateTime(detail.device.value.workerRuntime.updatedAt)
            "
          />
        </VanCellGroup>
      </section>

      <DeviceProviderSection
        :inventories="detail.provider.query.data.value"
        :initial-loading="detail.provider.isInitialLoading.value"
        :initial-error="detail.provider.isInitialError.value"
        :background-error="detail.provider.isBackgroundError.value"
        :error-message="detail.provider.errorMessage.value"
        @retry="detail.provider.query.refetch"
      />

      <DeviceSkillSummary
        :capabilities="detail.capability.query.data.value"
        :initial-loading="detail.capability.isInitialLoading.value"
        :initial-error="detail.capability.isInitialError.value"
        :background-error="detail.capability.isBackgroundError.value"
        :error-message="detail.capability.errorMessage.value"
        @retry="detail.capability.query.refetch"
      />

      <VanCollapse v-model="expanded">
        <VanCollapseItem title="更多信息" name="device-details">
          <dl class="device-detail-page__details">
            <div>
              <dt>设备 ID</dt>
              <dd>{{ detail.device.value.deviceId }}</dd>
            </div>
            <div>
              <dt>位置</dt>
              <dd>{{ detail.device.value.location || '—' }}</dd>
            </div>
            <div>
              <dt>备注</dt>
              <dd>{{ detail.device.value.note || '—' }}</dd>
            </div>
          </dl>
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
  gap: var(--space-2);
  margin: 0;
}

.device-detail-page__details div {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: var(--space-2);
}

.device-detail-page__details dt {
  color: var(--text-secondary);
}

.device-detail-page__details dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
}
</style>
