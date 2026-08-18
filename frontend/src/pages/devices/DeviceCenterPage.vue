<script setup lang="ts">
import {
  DeviceDetailDrawer,
  DeviceFilterBar,
  DeviceFormDialog,
  DeviceListTable,
  useDeviceManagement,
} from '@/features/device-management'
import PageHeader from '@/shared/components/PageHeader.vue'
import PageSection from '@/shared/components/PageSection.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'
import StatCard from '@/shared/components/StatCard.vue'
import SummaryGrid from '@/shared/components/SummaryGrid.vue'
import AppButton from '@/shared/ui/AppButton.vue'

const management = useDeviceManagement()
</script>

<template>
  <div class="page-container device-center-page">
    <PageHeader
      title="设备中心"
      description="统一管理执行设备、运行状态与自动化能力"
    >
      <template #actions>
        <AppButton tone="primary" @click="management.openCreate"
          >添加设备</AppButton
        >
      </template>
    </PageHeader>

    <SummaryGrid aria-label="设备统计">
      <StatCard label="设备总数" :value="management.statistics.value.total" />
      <StatCard
        label="本页已启用"
        :value="management.statistics.value.enabled"
        tone="success"
      />
      <StatCard
        label="本页已停用"
        :value="management.statistics.value.disabled"
      />
      <StatCard label="Worker 运行状态" value="未接入" />
    </SummaryGrid>

    <DeviceFilterBar
      v-model="management.filterDraft.value"
      :available="management.filtersAvailable"
      @query="management.query"
      @reset="management.resetFilters"
    />

    <PageSection
      title="设备列表"
      :description="management.dataSourceDescription"
    >
      <div class="device-list-pattern">
        <DeviceListTable
          :rows="management.rows.value"
          :loading="management.listLoading.value"
          :error="management.listError.value"
          @view="management.openDetail"
          @edit="management.openEdit"
          @retry="management.retryList"
        />
        <PaginationBar
          v-model:page="management.page.value"
          :page-size="management.pageSize.value"
          :item-count="management.total.value"
          @update:page-size="management.setPageSize"
        />
      </div>
    </PageSection>

    <DeviceDetailDrawer
      v-model:show="management.detailVisible.value"
      :device="management.detailDevice.value"
      :loading="management.detailLoading.value"
      :error="management.detailError.value"
      @retry="management.retryDetail"
    />

    <DeviceFormDialog
      v-model:show="management.formVisible.value"
      :mode="management.formMode.value"
      :initial-value="management.formInitialValue.value"
      :submitting="management.formSubmitting.value"
      @save="management.saveDevice"
    />
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
