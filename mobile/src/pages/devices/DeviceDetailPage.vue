<script setup lang="ts">
import {
  Button as VanButton,
  Empty as VanEmpty,
  Skeleton as VanSkeleton,
  showToast,
} from 'vant'
import { computed, onScopeDispose, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { MOBILE_ROUTE_NAMES } from '@/app/router/routes'
import { TaskListCard } from '@/entities/task'
import {
  DeviceCapabilityPanel,
  DeviceDetailHero,
  DeviceMoreSheet,
  mapDeviceActiveTaskToTaskListItem,
  type DeviceActiveTaskState,
  useDeviceDetail,
} from '@/features/device-center'
import { AppPage, useMobileDetailHeaderAction } from '@/shared/ui'

const route = useRoute()
const router = useRouter()
const deviceId = computed(() => String(route.params.deviceId ?? ''))
const detail = useDeviceDetail(deviceId)
const detailHeader = useMobileDetailHeaderAction()
const moreSheetOpen = ref(false)

const activeTaskState = computed<DeviceActiveTaskState>(() => ({
  task: detail.activeTask.query.data.value,
  hasSuccessfulData: detail.activeTask.query.data.value !== undefined,
  initialLoading: detail.activeTask.isInitialLoading.value,
  initialError: detail.activeTask.isInitialError.value,
  backgroundError: detail.activeTask.isBackgroundError.value,
  retry: () => {
    void detail.activeTask.query.refetch()
  },
}))
const activeTaskCard = computed(() => {
  const task = detail.activeTask.query.data.value
  const device = detail.device.value

  return task && device
    ? mapDeviceActiveTaskToTaskListItem(task, device.displayName)
    : null
})
const capabilityRefreshing = computed(
  () =>
    Boolean(detail.provider.query.isFetching?.value) ||
    Boolean(detail.capability.query.isFetching?.value),
)

watch(
  () => detail.device.value,
  (device) => {
    detailHeader?.setAction(
      device
        ? {
            label: '更多信息',
            icon: 'more',
            run: () => {
              moreSheetOpen.value = true
            },
          }
        : null,
    )
  },
  { immediate: true },
)

onScopeDispose(() => {
  detailHeader?.setAction(null)
})

function openTask(taskId: string): void {
  void router.push({
    name: MOBILE_ROUTE_NAMES.taskDetail,
    params: { taskId },
    query: { fromDeviceId: deviceId.value },
  })
}

async function refreshCapabilities(): Promise<void> {
  await Promise.all([
    detail.provider.query.refetch(),
    detail.capability.query.refetch(),
  ])
}

function showActionPlaceholder(): void {
  showToast('功能建设中')
}
</script>

<template>
  <AppPage
    class="device-detail-page"
    label="设备详情内容"
    data-testid="device-detail"
  >
    <div
      v-if="detail.isDeviceInitialLoading.value"
      class="device-detail-page__initial-state"
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
      <DeviceDetailHero
        :device="detail.device.value"
        :active-task-state="activeTaskState"
        :inventories="detail.provider.query.data.value"
      />

      <section
        class="device-detail-page__current-task"
        data-testid="device-current-task"
      >
        <h2 class="device-detail-page__section-title">当前任务</h2>
        <div
          v-if="detail.activeTask.isInitialLoading.value"
          class="device-detail-page__task-state"
          data-testid="device-current-task-loading"
        >
          <VanSkeleton title :row="2" />
        </div>
        <div
          v-else-if="detail.activeTask.isInitialError.value"
          class="device-detail-page__task-state device-detail-page__task-state--error"
          data-testid="device-current-task-error"
        >
          <span>加载失败</span>
          <VanButton @click="detail.activeTask.query.refetch">重试</VanButton>
        </div>
        <TaskListCard
          v-else-if="activeTaskCard"
          :task="activeTaskCard"
          visual-v2
          button-test-id="device-current-task-link"
          @select="openTask"
        />
        <p
          v-else
          class="device-detail-page__task-state device-detail-page__task-state--idle"
          data-testid="device-current-task-idle"
        >
          空闲
        </p>
      </section>

      <DeviceCapabilityPanel
        :inventories="detail.provider.query.data.value"
        :capabilities="detail.capability.query.data.value"
        :provider-loading="detail.provider.isInitialLoading.value"
        :provider-error="detail.provider.isInitialError.value"
        :capability-loading="detail.capability.isInitialLoading.value"
        :capability-error="detail.capability.isInitialError.value"
        :refreshing="capabilityRefreshing"
        @refresh-capability="refreshCapabilities"
        @retry-provider="detail.provider.query.refetch"
        @retry-capability="detail.capability.query.refetch"
        @configure-application="showActionPlaceholder"
        @run-application="showActionPlaceholder"
        @configure-skill="showActionPlaceholder"
        @run-skill="showActionPlaceholder"
      />

      <DeviceMoreSheet
        v-model:show="moreSheetOpen"
        :device="detail.device.value"
        :inventories="detail.provider.query.data.value"
        :capabilities="detail.capability.query.data.value"
      />
    </template>
  </AppPage>
</template>

<style scoped>
.device-detail-page.app-page {
  gap: var(--visual-v2-detail-section-gap);
  padding: var(--visual-v2-detail-content-padding-top)
    max(var(--visual-v2-detail-content-padding-x), var(--safe-area-right))
    var(--visual-v2-detail-content-padding-bottom)
    max(var(--visual-v2-detail-content-padding-x), var(--safe-area-left));
  color: var(--visual-v2-page-text-primary);
  background: transparent;
}

.device-detail-page__initial-state {
  min-height: var(--layout-inline-state-min-height);
}

.device-detail-page__current-task {
  display: grid;
  min-width: 0;
  gap: var(--visual-v2-detail-section-title-gap);
}

.device-detail-page__section-title {
  margin-left: var(--layout-compact-gap);
  font-size: var(--typography-v2-detail-section-title-size);
  font-weight: var(--typography-v2-detail-section-title-weight);
  line-height: var(--typography-v2-detail-section-title-line-height);
  letter-spacing: var(--typography-v2-business-card-title-letter-spacing);
}

.device-detail-page__task-state {
  min-height: var(--visual-v2-business-card-min-height);
  padding: var(--visual-v2-business-card-padding-top)
    var(--visual-v2-business-card-padding-right)
    var(--visual-v2-business-card-padding-bottom)
    var(--visual-v2-business-card-padding-left);
  color: var(--text-secondary);
  background: var(--visual-v2-detail-surface-background);
  border: var(--visual-v2-business-card-border-width) solid
    var(--visual-v2-detail-surface-border-color);
  border-radius: var(--visual-v2-business-card-radius);
  box-shadow: var(--visual-v2-detail-surface-shadow);
}

.device-detail-page__task-state--error {
  display: flex;
  gap: var(--layout-content-gap);
  align-items: center;
  justify-content: center;
}

.device-detail-page__task-state--idle {
  display: grid;
  place-items: center;
}
</style>
