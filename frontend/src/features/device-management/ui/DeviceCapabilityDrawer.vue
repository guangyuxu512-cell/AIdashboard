<script setup lang="ts">
import type { DataTableColumns } from 'naive-ui'
import { computed, h } from 'vue'

import {
  DeviceConnectionStatusTag,
  DeviceEnabledStatusTag,
  type DeviceListItemViewModel,
  type DeviceSkillCapabilityViewModel,
  type ProviderApplicationViewModel,
  type YingdaoInventoryViewModel,
  YingdaoAvailabilityStatusTag,
  YingdaoProviderStatusTag,
} from '@/entities/device'
import DataTable from '@/shared/components/DataTable.vue'
import DetailDrawer from '@/shared/components/DetailDrawer.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import AppButton from '@/shared/ui/AppButton.vue'

import DeviceCapabilityCard from './DeviceCapabilityCard.vue'
import YingdaoApplicationsTable from './YingdaoApplicationsTable.vue'

const props = defineProps<{
  show: boolean
  device: DeviceListItemViewModel | null
  skills: DeviceSkillCapabilityViewModel[]
  skillsLoading?: boolean
  skillsError?: string | null
  yingdaoInventory?: YingdaoInventoryViewModel | null
  providerInventoryLoading?: boolean
  providerInventoryError?: string | null
  yingdaoRefreshing?: boolean
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  'retry-skills': []
  'retry-provider-inventory': []
  'refresh-yingdao': []
  configure: [application: ProviderApplicationViewModel]
  run: [application: ProviderApplicationViewModel]
}>()

const hasYingdaoRunSkill = computed(() =>
  props.skills.some((skill) => skill.skillId === 'yingdao.app.run'),
)
const providerReady = computed(
  () =>
    props.yingdaoInventory?.providerStatus === 'ready' &&
    props.yingdaoInventory.executionAvailable,
)
const deviceReady = computed(
  () =>
    Boolean(props.device?.enabled) &&
    ['online', 'busy'].includes(props.device?.runtimeStatus ?? ''),
)
const canRunApplications = computed(
  () => hasYingdaoRunSkill.value && providerReady.value && deviceReady.value,
)
const runUnavailableReason = computed(() => {
  if (!hasYingdaoRunSkill.value) return '当前 Worker 未声明 yingdao.app.run Skill'
  if (!providerReady.value) return '影刀 Provider 尚未就绪'
  if (!deviceReady.value) return '设备离线或已停用，不能创建即时执行任务'
  return null
})

function skillStatus() {
  if (!props.device?.enabled) return { label: '已安装', tone: 'neutral' as const }
  if (!['online', 'busy'].includes(props.device.runtimeStatus)) {
    return { label: '最后已知', tone: 'warning' as const }
  }
  return { label: '可用', tone: 'success' as const }
}

const skillColumns: DataTableColumns<DeviceSkillCapabilityViewModel> = [
  { title: 'Skill 名称', key: 'displayName', minWidth: 150 },
  {
    title: 'Skill ID',
    key: 'skillId',
    minWidth: 180,
    ellipsis: { tooltip: true },
  },
  {
    title: 'Runtime',
    key: 'runtime',
    width: 100,
    render: (skill) =>
      ({ python: 'Python', rpa: 'RPA', discovery: 'Discovery' })[skill.runtime],
  },
  {
    title: 'Provider',
    key: 'provider',
    width: 100,
    render: (skill) => skill.provider ?? 'System',
  },
  { title: 'Version', key: 'version', width: 90 },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: () => {
      const meta = skillStatus()
      return h(StatusTag, { label: meta.label, tone: meta.tone })
    },
  },
]
</script>

<template>
  <DetailDrawer
    :show="show"
    :title="`设备能力${device ? ` · ${device.deviceName}` : ''}`"
    size="lg"
    @update:show="$emit('update:show', $event)"
  >
    <div v-if="device" class="device-capability">
      <div class="device-capability__summary">
        <span>Worker</span>
        <DeviceConnectionStatusTag :status="device.runtimeStatus" />
        <DeviceEnabledStatusTag :status="device.enabledStatus" />
      </div>

      <section class="device-capability__section">
        <div class="device-capability__section-heading">
          <div>
            <h3>已注册 Skill</h3>
            <p>Worker 当前声明的可执行能力；离线时保留最后一次已知快照。</p>
          </div>
        </div>
        <LoadingState v-if="skillsLoading" description="正在读取 Skill 能力…" />
        <ErrorState
          v-else-if="skillsError"
          :description="skillsError"
          retryable
          @retry="$emit('retry-skills')"
        />
        <DataTable
          v-else
          :columns="skillColumns"
          :data="skills"
          :row-key="(row: DeviceSkillCapabilityViewModel) => row.skillId"
          :scroll-x="720"
          empty-description="当前 Worker 尚未上报 Skill 能力"
        />
      </section>

      <section class="device-capability__section">
        <div class="device-capability__section-heading">
          <div>
            <h3>影刀应用</h3>
            <p>ShadowBot 6.3.6 当前账号可访问的云端 Application，不等同于 Skill。</p>
          </div>
        </div>
        <DeviceCapabilityCard
          title="影刀 RPA"
          description="Provider 状态与当前会话"
        >
          <template #status>
            <YingdaoProviderStatusTag
              v-if="yingdaoInventory"
              :status="yingdaoInventory.providerStatus"
            />
            <YingdaoAvailabilityStatusTag v-else status="not_detected" />
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
              <dt>版本</dt>
              <dd>{{ yingdaoInventory?.providerVersion ?? '—' }}</dd>
            </div>
            <div>
              <dt>账号</dt>
              <dd>{{ yingdaoInventory?.accountDisplay ?? '—' }}</dd>
            </div>
            <div>
              <dt>状态</dt>
              <dd>{{ providerReady ? '已就绪' : '未就绪' }}</dd>
            </div>
            <div>
              <dt>云端应用</dt>
              <dd>{{ yingdaoInventory?.applicationCount ?? '—' }}</dd>
            </div>
          </dl>

          <template #actions>
            <AppButton
              :loading="yingdaoRefreshing"
              :disabled="!deviceReady"
              @click="$emit('refresh-yingdao')"
            >
              刷新影刀能力
            </AppButton>
          </template>
        </DeviceCapabilityCard>

        <p v-if="runUnavailableReason" class="device-capability__notice">
          {{ runUnavailableReason }}
        </p>
        <YingdaoApplicationsTable
          v-if="providerReady"
          :applications="yingdaoInventory?.applications ?? []"
          :can-run="canRunApplications"
          @configure="emit('configure', $event)"
          @run="emit('run', $event)"
        />
        <EmptyState
          v-else-if="!providerInventoryLoading && !providerInventoryError"
          description="影刀 Provider 就绪后显示当前账号的云端应用"
        />
      </section>
    </div>

    <template #footer>
      <AppButton @click="$emit('update:show', false)">关闭</AppButton>
    </template>
  </DetailDrawer>
</template>

<style scoped>
.device-capability {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-6);
}

.device-capability__summary {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.device-capability__summary > span {
  margin-right: var(--space-1);
  color: var(--text-secondary);
}

.device-capability__section {
  min-width: 0;
}

.device-capability__section-heading {
  display: flex;
  margin-bottom: var(--space-3);
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.device-capability__section h3,
.device-capability__section p {
  margin: 0;
}

.device-capability__section h3 {
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
}

.device-capability__section-heading p,
.device-capability__notice,
.capability-facts dt {
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.device-capability__section-heading p {
  margin-top: var(--space-1);
}

.capability-facts {
  display: grid;
  margin: 0;
  gap: var(--space-3) var(--space-5);
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.capability-facts dd {
  margin: var(--space-1) 0 0;
}

.device-capability__notice {
  margin: var(--space-3) 0;
}

@media (max-width: 720px) {
  .capability-facts {
    grid-template-columns: 1fr;
  }
}
</style>
