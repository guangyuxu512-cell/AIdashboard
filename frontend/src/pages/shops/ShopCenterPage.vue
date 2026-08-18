<script setup lang="ts">
import {
  ShopDetailDrawer,
  ShopFilterBar,
  ShopFormDialog,
  ShopListTable,
  useShopManagement,
} from '@/features/shop-management'
import PageHeader from '@/shared/components/PageHeader.vue'
import PageSection from '@/shared/components/PageSection.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'
import StatCard from '@/shared/components/StatCard.vue'
import SummaryGrid from '@/shared/components/SummaryGrid.vue'
import AppButton from '@/shared/ui/AppButton.vue'

const management = useShopManagement()
const isDevelopment = import.meta.env.DEV
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
        label="本页已启用"
        :value="management.statistics.value.enabled"
        tone="success"
      />
      <StatCard
        label="本页已停用"
        :value="management.statistics.value.disabled"
      />
      <StatCard label="会话 / 自动化" value="未接入" />
    </SummaryGrid>

    <ShopFilterBar
      v-if="management.filtersAvailable || isDevelopment"
      v-model="management.filterDraft.value"
      :available="management.filtersAvailable"
      :platform-options="management.platformOptions"
      :owner-options="management.ownerOptions.value"
      :owner-options-loading="management.ownerOptionsLoading.value"
      @query="management.query"
      @reset="management.resetFilters"
    />

    <PageSection
      title="店铺列表"
      :description="
        isDevelopment ? management.dataSourceDescription : undefined
      "
    >
      <div class="shop-list-pattern">
        <ShopListTable
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

    <ShopDetailDrawer
      v-model:show="management.detailVisible.value"
      :shop="management.detailShop.value"
      :loading="management.detailLoading.value"
      :error="management.detailError.value"
      @retry="management.retryDetail"
    />

    <ShopFormDialog
      v-model:show="management.formVisible.value"
      :mode="management.formMode.value"
      :initial-value="management.formInitialValue.value"
      :platform-options="management.platformOptions"
      :owner-options="management.ownerOptions.value"
      :owner-options-loading="management.ownerOptionsLoading.value"
      :submitting="management.formSubmitting.value"
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
