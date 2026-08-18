<script setup lang="ts">
import {
  AddDeviceInfoDialog,
  DeviceDetailDrawer,
  DeviceFilterBar,
  DeviceListTable,
  useDeviceManagementMock,
} from '@/features/device-management'
import PageHeader from '@/shared/components/PageHeader.vue'
import PageSection from '@/shared/components/PageSection.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'
import StatCard from '@/shared/components/StatCard.vue'
import SummaryGrid from '@/shared/components/SummaryGrid.vue'
import AppButton from '@/shared/ui/AppButton.vue'

const management = useDeviceManagementMock()
</script>

<template>
  <div class="page-container device-center-page">
    <PageHeader
      title="设备中心"
      description="统一管理执行设备、运行状态与自动化能力"
    >
      <template #actions>
        <AppButton tone="primary" @click="management.openAddInfo"
          >添加设备</AppButton
        >
      </template>
    </PageHeader>

    <SummaryGrid aria-label="设备统计">
      <StatCard
        label="在线设备"
        :value="management.statistics.value.online"
        tone="success"
      />
      <StatCard label="离线设备" :value="management.statistics.value.offline" />
      <StatCard
        label="忙碌设备"
        :value="management.statistics.value.busy"
        tone="primary"
      />
      <StatCard
        label="异常设备"
        :value="management.statistics.value.error"
        tone="error"
      />
    </SummaryGrid>

    <DeviceFilterBar
      v-model="management.filterDraft.value"
      @query="management.query"
      @reset="management.resetFilters"
    />

    <PageSection
      title="设备列表"
      description="当前运行、资源与心跳信息均来自 Frontend Fixture。"
    >
      <div class="device-list-pattern">
        <DeviceListTable
          :rows="management.pagedDevices.value"
          @view="management.openDetail"
        />
        <PaginationBar
          v-model:page="management.page.value"
          v-model:page-size="management.pageSize.value"
          :item-count="management.filteredDevices.value.length"
        />
      </div>
    </PageSection>

    <DeviceDetailDrawer
      v-model:show="management.detailVisible.value"
      :device="management.detailDevice.value"
    />

    <AddDeviceInfoDialog v-model:show="management.addInfoVisible.value" />
  </div>
</template>

<style scoped>
.device-list-pattern {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-4);
}
</style>
