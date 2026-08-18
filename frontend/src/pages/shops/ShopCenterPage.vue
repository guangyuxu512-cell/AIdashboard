<script setup lang="ts">
import {
  ShopDetailDrawer,
  ShopFilterBar,
  ShopFormDialog,
  ShopListTable,
  useShopManagementMock,
} from '@/features/shop-management'
import PageHeader from '@/shared/components/PageHeader.vue'
import PageSection from '@/shared/components/PageSection.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'
import StatCard from '@/shared/components/StatCard.vue'
import SummaryGrid from '@/shared/components/SummaryGrid.vue'
import AppButton from '@/shared/ui/AppButton.vue'

const management = useShopManagementMock()
</script>

<template>
  <div class="page-container shop-center-page">
    <PageHeader
      title="店铺中心"
      description="统一管理平台店铺、会话状态与执行配置"
    >
      <template #actions>
        <AppButton tone="primary" @click="management.openCreate"
          >新增店铺</AppButton
        >
      </template>
    </PageHeader>

    <SummaryGrid aria-label="店铺统计">
      <StatCard label="店铺总数" :value="management.statistics.value.total" />
      <StatCard
        label="正常店铺"
        :value="management.statistics.value.normal"
        tone="success"
      />
      <StatCard
        label="会话异常"
        :value="management.statistics.value.sessionWarning"
        tone="error"
      />
      <StatCard
        label="自动化运行中"
        :value="management.statistics.value.automationRunning"
        tone="primary"
      />
    </SummaryGrid>

    <ShopFilterBar
      v-model="management.filterDraft.value"
      @query="management.query"
      @reset="management.resetFilters"
    />

    <PageSection
      title="店铺列表"
      description="当前数据来自 Frontend Fixture，仅用于界面验证。"
    >
      <div class="shop-list-pattern">
        <ShopListTable
          :rows="management.pagedShops.value"
          @view="management.openDetail"
          @edit="management.openEdit"
        />
        <PaginationBar
          v-model:page="management.page.value"
          v-model:page-size="management.pageSize.value"
          :item-count="management.filteredShops.value.length"
        />
      </div>
    </PageSection>

    <ShopDetailDrawer
      v-model:show="management.detailVisible.value"
      :shop="management.detailShop.value"
    />

    <ShopFormDialog
      v-model:show="management.formVisible.value"
      :mode="management.formMode.value"
      :initial-value="management.formInitialValue.value"
      @save="management.saveShop"
    />
  </div>
</template>

<style scoped>
.shop-list-pattern {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-4);
}
</style>
