<script setup lang="ts">
import type { DataTableColumns } from 'naive-ui'
import { computed } from 'vue'
import { DeviceConnectionStatusTag, DeviceEnabledStatusTag, type DeviceListItemViewModel, type DeviceSkillCapabilityViewModel } from '@/entities/device'
import DataTable from '@/shared/components/DataTable.vue'
import DetailDrawer from '@/shared/components/DetailDrawer.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'
import AppButton from '@/shared/ui/AppButton.vue'

const props = defineProps<{
  show: boolean
  device: DeviceListItemViewModel | null
  skills: DeviceSkillCapabilityViewModel[]
  skillsLoading?: boolean
  skillsError?: string | null
}>()
defineEmits<{ 'update:show': [value: boolean]; 'retry-skills': [] }>()
const businessSkills = computed(() => props.skills.filter((skill) => skill.classification === 'business' && !skill.skillId.startsWith('yingdao.')))
const columns: DataTableColumns<DeviceSkillCapabilityViewModel> = [
  { title: '技能名称', key: 'displayName', minWidth: 150 },
  { title: '技能 ID', key: 'skillId', minWidth: 180, ellipsis: { tooltip: true } },
  { title: '版本', key: 'version', width: 100 },
]
</script>

<template>
  <DetailDrawer :show="show" :title="`设备能力${device ? ` · ${device.deviceName}` : ''}`"
    size="lg" @update:show="$emit('update:show', $event)">
    <div v-if="device" class="device-capability">
      <div class="device-capability__summary">
        <span>Worker</span>
        <DeviceConnectionStatusTag :status="device.runtimeStatus" />
        <DeviceEnabledStatusTag :status="device.enabledStatus" />
      </div>
      <h3>Worker 技能</h3>
      <p>显示设备上报的技能；离线时显示上次上报结果。</p>
      <LoadingState v-if="skillsLoading" description="正在读取技能…" />
      <ErrorState v-else-if="skillsError" :description="skillsError" retryable @retry="$emit('retry-skills')" />
      <EmptyState v-else-if="businessSkills.length === 0" description="当前 Worker 尚未上报业务技能" />
      <DataTable v-else :columns="columns" :data="businessSkills"
        :row-key="(row: DeviceSkillCapabilityViewModel) => row.skillId" :scroll-x="430" />
    </div>
    <template #footer><AppButton @click="$emit('update:show', false)">关闭</AppButton></template>
  </DetailDrawer>
</template>

<style scoped>
.device-capability { display: flex; min-width: 0; flex-direction: column; gap: var(--space-3); }
.device-capability__summary { display: flex; align-items: center; gap: var(--space-2); }
</style>
