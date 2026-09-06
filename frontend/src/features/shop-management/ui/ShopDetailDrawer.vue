<script setup lang="ts">
import { NDescriptions, NDescriptionsItem } from 'naive-ui'

import { ShopStatusTag, type ShopListItemViewModel } from '@/entities/shop'
import { getPlatformDefinition, PlatformDisplay } from '@/entities/platform'
import DetailDrawer from '@/shared/components/DetailDrawer.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'
import AppButton from '@/shared/ui/AppButton.vue'

import ShopConnectionSection from './ShopConnectionSection.vue'
import ShopDeviceBindingSection from './ShopDeviceBindingSection.vue'

defineProps<{
  show: boolean
  shop: ShopListItemViewModel | null
  loading?: boolean
  error?: string | null
}>()

defineEmits<{
  'update:show': [value: boolean]
  retry: []
  edit: [shop: ShopListItemViewModel]
  sessionUpdated: []
}>()
</script>

<template>
  <DetailDrawer
    :show="show"
    title="店铺详情"
    size="sm"
    @update:show="$emit('update:show', $event)"
  >
    <template v-if="shop" #header>
      <div class="shop-detail-header">
        <PlatformDisplay :code="shop.platform" :label="false" />
        <div class="shop-detail-header__identity">
          <strong>{{ shop.shopName }}</strong>
          <span>{{ getPlatformDefinition(shop.platform)?.label }}</span>
        </div>
        <AppButton tone="text" @click="$emit('edit', shop)">编辑</AppButton>
      </div>
    </template>

    <LoadingState v-if="loading" description="正在加载店铺详情…" />
    <ErrorState
      v-else-if="error"
      :description="error"
      retryable
      @retry="$emit('retry')"
    />
    <div v-else-if="shop" class="shop-detail">
      <section class="shop-detail__section">
        <h3>基本信息</h3>
        <NDescriptions :column="1" label-placement="left" bordered>
          <NDescriptionsItem label="平台店铺名称">{{
            shop.shopName
          }}</NDescriptionsItem>
          <NDescriptionsItem label="平台">
            <PlatformDisplay :code="shop.platform" />
          </NDescriptionsItem>
          <NDescriptionsItem label="负责人">{{
            shop.ownerName
          }}</NDescriptionsItem>
          <NDescriptionsItem label="平台店铺 ID">
            <span class="shop-detail__id">{{
              shop.platformShopId ?? '—'
            }}</span>
          </NDescriptionsItem>
          <NDescriptionsItem label="中控台 Shop ID">
            <span class="shop-detail__id">{{ shop.shopId }}</span>
          </NDescriptionsItem>
          <NDescriptionsItem label="基础状态">
            <ShopStatusTag :status="shop.enabledStatus" />
          </NDescriptionsItem>
          <NDescriptionsItem label="备注">{{
            shop.note || '—'
          }}</NDescriptionsItem>
          <NDescriptionsItem label="创建时间">{{
            shop.createdAtDisplay
          }}</NDescriptionsItem>
          <NDescriptionsItem label="更新时间">{{
            shop.updatedAtDisplay
          }}</NDescriptionsItem>
        </NDescriptions>
      </section>

      <ShopConnectionSection
        :shop="shop"
        @session-updated="$emit('sessionUpdated')"
      />

      <ShopDeviceBindingSection :shop="shop" />

      <section class="shop-detail__section">
        <h3>操作记录</h3>
        <EmptyState description="暂无操作记录" />
      </section>
    </div>

    <template #footer>
      <AppButton @click="$emit('update:show', false)">关闭</AppButton>
    </template>
  </DetailDrawer>
</template>

<style scoped>
.shop-detail-header {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--space-2);
}

.shop-detail-header__identity {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: var(--space-1);
}

.shop-detail-header__identity strong,
.shop-detail-header__identity span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.shop-detail-header__identity strong {
  color: var(--text-primary);
  font-size: var(--font-size-body);
}

.shop-detail-header__identity span {
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
}

.shop-detail {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-5);
}

.shop-detail__section {
  min-width: 0;
}

.shop-detail__section h3 {
  margin-bottom: var(--space-3);
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
}

.shop-detail__id {
  overflow-wrap: anywhere;
  color: var(--text-secondary);
  font-family: monospace;
  font-size: var(--font-size-secondary);
}
</style>
