<script setup lang="ts">
import {
  Button as VanButton,
  Cell as VanCell,
  CellGroup as VanCellGroup,
  Collapse as VanCollapse,
  CollapseItem as VanCollapseItem,
  Empty as VanEmpty,
  Skeleton as VanSkeleton,
  showToast,
} from 'vant'
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { MOBILE_ROUTE_NAMES } from '@/app/router/routes'
import { formatDeviceDateTime } from '@/entities/device'
import {
  ActiveTaskSummary,
  DeviceCapabilityPanel,
  DeviceProviderDetails,
  DeviceSkillDetails,
  DeviceYingdaoSummary,
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

function showActionPlaceholder(): void {
  showToast('功能建设中')
}
</script>

<template>
  <AppPage class="device-detail-page" label="设备详情内容">
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
      <DeviceYingdaoSummary
        :device="detail.device.value"
        :inventories="detail.provider.query.data.value"
        :provider-loading="detail.provider.isInitialLoading.value"
        :provider-error="detail.provider.isInitialError.value"
        @retry-provider="detail.provider.query.refetch"
      />

      <DeviceCapabilityPanel
        :inventories="detail.provider.query.data.value"
        :capabilities="detail.capability.query.data.value"
        :provider-loading="detail.provider.isInitialLoading.value"
        :provider-error="detail.provider.isInitialError.value"
        :capability-loading="detail.capability.isInitialLoading.value"
        :capability-error="detail.capability.isInitialError.value"
        @refresh-capability="showActionPlaceholder"
        @retry-provider="detail.provider.query.refetch"
        @retry-capability="detail.capability.query.refetch"
        @configure-application="showActionPlaceholder"
        @run-application="showActionPlaceholder"
        @configure-skill="showActionPlaceholder"
        @run-skill="showActionPlaceholder"
      />

      <section
        class="device-detail-page__section mobile-section-surface"
        data-testid="device-current-task"
      >
        <h2>当前任务</h2>
        <ActiveTaskSummary
          :task="detail.activeTask.query.data.value"
          :initial-loading="detail.activeTask.isInitialLoading.value"
          :initial-error="detail.activeTask.isInitialError.value"
          compact
          @retry="detail.activeTask.query.refetch"
          @select="openTask"
        />
      </section>

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
                <VanCell
                  title="设备更新时间"
                  :value="formatDeviceDateTime(detail.device.value.updatedAt)"
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

.device-detail-page__section,
.device-detail-page__details section {
  display: grid;
  min-width: 0;
  gap: var(--space-3);
}

.device-detail-page__section {
  padding: var(--space-3);
}

.device-detail-page__details {
  display: grid;
  gap: var(--space-4);
}

.device-detail-page__section h2,
.device-detail-page__details h3 {
  font-size: var(--font-size-label);
  line-height: var(--line-height-label);
}

.device-detail-page__section :deep(.van-cell-group) {
  border: 0;
  border-radius: 0;
}
</style>
