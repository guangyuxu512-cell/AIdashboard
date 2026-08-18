<script setup lang="ts">
import {
  ShopDetailDrawer,
  ShopBatchToolbar,
  ShopFilterBar,
  ShopFormDialog,
  ShopListTable,
  ShopPlatformSwitchBar,
  useShopManagement,
} from '@/features/shop-management'
import PageSection from '@/shared/components/PageSection.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'
import AppButton from '@/shared/ui/AppButton.vue'

const management = useShopManagement()
</script>

<template>
  <div class="page-container shop-center-page">
    <ShopPlatformSwitchBar v-model="management.selectedPlatform.value" />

    <ShopFilterBar
      v-model="management.filterDraft.value"
      :owner-options="management.ownerOptions.value"
      :owner-options-loading="management.ownerOptionsLoading.value"
      @query="management.query"
      @reset="management.resetFilters"
    >
      <template #primary-action>
        <AppButton tone="primary" @click="management.openCreate">
          + 新增店铺
        </AppButton>
      </template>
    </ShopFilterBar>

    <PageSection class="shop-list-section" fill>
      <div class="shop-list-pattern">
        <ShopBatchToolbar
          :selected-count="management.selectedShopCount.value"
        />
        <ShopListTable
          v-model:checked-row-keys="management.selectedShopIds.value"
          :rows="management.rows.value"
          :loading="management.listLoading.value"
          :error="management.listError.value"
          @view="management.openDetail"
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
      @edit="management.editFromDetail"
      @retry="management.retryDetail"
    />

    <ShopFormDialog
      v-model:show="management.formVisible.value"
      :mode="management.formMode.value"
      :initial-value="management.formInitialValue.value"
      :owner-options="management.ownerOptions.value"
      :owner-options-loading="management.ownerOptionsLoading.value"
      :submitting="management.formSubmitting.value"
      @save="management.saveShop"
    />
  </div>
</template>

<style scoped>
.shop-center-page {
  height: 100%;
  min-height: 0;
}

.shop-list-pattern {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: var(--space-4);
}
</style>
