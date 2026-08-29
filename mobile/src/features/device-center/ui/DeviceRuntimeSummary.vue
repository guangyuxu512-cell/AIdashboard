<script setup lang="ts">
import {
  Button as VanButton,
  Icon as VanIcon,
  Loading as VanLoading,
  Tag as VanTag,
} from 'vant'
import { computed } from 'vue'

import {
  DeviceConnectionTag,
  formatRelativeHeartbeat,
  type Device,
  type DeviceProviderInventoryReadDto,
} from '@/entities/device'
import {
  TASK_STATUS_META,
  type ActiveTaskSummaryReadDto,
} from '@/entities/task'

const props = defineProps<{
  device: Device
  activeTask: ActiveTaskSummaryReadDto | null | undefined
  activeTaskLoading: boolean
  activeTaskError: boolean
  inventories: DeviceProviderInventoryReadDto[] | undefined
  providerLoading: boolean
  providerError: boolean
}>()

const emit = defineEmits<{ retryProvider: [] }>()

const yingdao = computed(() =>
  props.inventories?.find((item) => item.provider_code === 'yingdao'),
)
const runtimeMeta = computed(() => {
  const runtime = props.device.workerRuntime
  if (!runtime) return 'Worker — · 未上报'
  return `Worker ${runtime.workerVersion || '—'} · ${formatRelativeHeartbeat(runtime.lastSeenAt)}`
})
const runtimeState = computed(() => {
  if (!props.device.enabled) {
    return { label: '停用', tagType: 'warning' as const }
  }
  if (props.activeTaskLoading) {
    return { label: '加载中', tagType: 'default' as const }
  }
  if (props.activeTaskError) {
    return { label: '—', tagType: 'default' as const }
  }
  if (props.activeTask) return TASK_STATUS_META[props.activeTask.status]
  if (props.activeTask === null) {
    return { label: '空闲', tagType: 'default' as const }
  }
  return { label: '—', tagType: 'default' as const }
})
const accountState = computed(() => {
  if (props.providerLoading) {
    return { label: '加载中', tagType: 'default' as const }
  }
  if (props.providerError) {
    return { label: '加载失败', tagType: 'danger' as const }
  }
  if (!yingdao.value) {
    return { label: '未上报', tagType: 'default' as const }
  }
  return yingdao.value.inventory.logged_in
    ? { label: '已登录', tagType: 'success' as const }
    : { label: '未登录', tagType: 'warning' as const }
})
const accountName = computed(() =>
  yingdao.value ? yingdao.value.account_display || '—' : '—',
)
const yingdaoVersion = computed(
  () => yingdao.value?.inventory.provider_version || null,
)
</script>

<template>
  <section
    class="device-runtime-summary mobile-card"
    data-testid="device-detail"
    aria-label="设备运行摘要"
  >
    <div
      class="device-runtime-summary__section"
      data-testid="device-summary-device"
    >
      <span
        class="device-runtime-summary__icon"
        data-testid="device-runtime-icon"
        aria-hidden="true"
      >
        <VanIcon name="desktop-o" />
      </span>
      <span class="device-runtime-summary__content">
        <strong
          class="device-runtime-summary__value"
          data-testid="device-runtime-name"
        >
          {{ device.displayName }}
        </strong>
        <span
          class="device-runtime-summary__states"
          data-testid="device-runtime-states"
        >
          <DeviceConnectionTag
            :status="device.workerRuntime?.connectionStatus"
          />
          <VanTag :type="runtimeState.tagType" round>
            {{ runtimeState.label }}
          </VanTag>
        </span>
        <span
          class="device-runtime-summary__meta"
          data-testid="device-runtime-meta"
        >
          {{ runtimeMeta }}
        </span>
      </span>
    </div>

    <div
      class="device-runtime-summary__separator"
      data-testid="device-runtime-summary-separator"
      role="separator"
    />

    <div
      class="device-runtime-summary__section"
      data-testid="device-summary-yingdao"
      :aria-busy="providerLoading"
    >
      <span
        class="device-runtime-summary__icon"
        data-testid="device-account-icon"
        aria-hidden="true"
      >
        <VanIcon name="manager-o" />
      </span>
      <span class="device-runtime-summary__content">
        <span class="device-runtime-summary__heading">
          <span class="device-runtime-summary__label">影刀账号</span>
          <VanLoading v-if="providerLoading" size="var(--icon-size-small)">
            加载中
          </VanLoading>
          <VanTag v-else :type="accountState.tagType" round>
            {{ accountState.label }}
          </VanTag>
        </span>
        <span
          class="device-runtime-summary__account-line"
          data-testid="device-account-line"
        >
          <strong
            class="device-runtime-summary__value device-runtime-summary__account-name"
            data-testid="device-account-name"
          >
            {{ accountName }}
          </strong>
          <template v-if="yingdaoVersion">
            <span
              class="device-runtime-summary__account-separator"
              aria-hidden="true"
            >
              ·
            </span>
            <span
              class="device-runtime-summary__account-version"
              data-testid="device-account-version"
            >
              {{ yingdaoVersion }}
            </span>
          </template>
          <VanButton
            v-if="providerError"
            class="device-runtime-summary__retry"
            @click="emit('retryProvider')"
          >
            重试
          </VanButton>
        </span>
      </span>
    </div>
  </section>
</template>

<style scoped>
.device-runtime-summary {
  display: grid;
  min-width: 0;
  padding: 0;
  overflow: hidden;
}

.device-runtime-summary__section {
  display: grid;
  min-width: 0;
  padding: var(--space-3);
  align-items: center;
  column-gap: var(--space-2);
  grid-template-columns: auto minmax(0, 1fr);
}

.device-runtime-summary__separator {
  height: var(--border-width);
  margin-inline: var(--space-3);
  background: var(--border-subtle);
}

.device-runtime-summary__icon {
  display: grid;
  width: var(--layout-runtime-summary-icon-slot-width);
  align-self: center;
  color: var(--text-secondary);
  font-size: var(--icon-size-runtime-summary);
  place-items: center;
}

.device-runtime-summary__content {
  display: grid;
  min-width: 0;
  gap: var(--space-1);
}

.device-runtime-summary__heading,
.device-runtime-summary__states,
.device-runtime-summary__account-line {
  display: flex;
  min-width: 0;
  gap: var(--space-1);
  align-items: center;
}

.device-runtime-summary__heading {
  justify-content: space-between;
}

.device-runtime-summary__label,
.device-runtime-summary__meta,
.device-runtime-summary__value {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-runtime-summary__label,
.device-runtime-summary__meta {
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

.device-runtime-summary__value {
  font-size: var(--font-size-label);
  line-height: var(--line-height-label);
}

.device-runtime-summary__states,
.device-runtime-summary__account-line {
  min-height: var(--line-height-body);
  overflow: hidden;
}

.device-runtime-summary__account-name {
  flex: 0 1 auto;
}

.device-runtime-summary__account-separator,
.device-runtime-summary__account-version {
  flex: 0 0 auto;
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
}

.device-runtime-summary__retry {
  width: max-content;
  min-width: var(--touch-target-min);
  height: var(--touch-target-min);
  padding: 0;
  color: var(--color-primary);
  background: transparent;
  border: 0;
}
</style>
