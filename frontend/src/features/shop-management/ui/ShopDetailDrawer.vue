<script setup lang="ts">
import { NDescriptions, NDescriptionsItem } from 'naive-ui'

import {
  SHOP_PLATFORM_META,
  ShopPlatformDisplay,
  ShopStatusTag,
  type ShopListItemViewModel,
} from '@/entities/shop'
import DetailDrawer from '@/shared/components/DetailDrawer.vue'
import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'
import AppButton from '@/shared/ui/AppButton.vue'

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
        <ShopPlatformDisplay :platform="shop.platform" :label="false" />
        <div class="shop-detail-header__identity">
          <strong>{{ shop.shopName }}</strong>
          <span>
            {{ SHOP_PLATFORM_META[shop.platform].label }} · {{ shop.shopId }}
          </span>
        </div>
        <ShopStatusTag :status="shop.enabledStatus" />
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
          <NDescriptionsItem label="店铺名称">{{
            shop.shopName
          }}</NDescriptionsItem>
          <NDescriptionsItem label="平台">
            <ShopPlatformDisplay :platform="shop.platform" />
          </NDescriptionsItem>
          <NDescriptionsItem label="负责人">{{
            shop.ownerName
          }}</NDescriptionsItem>
          <NDescriptionsItem label="店铺 ID">
            <span class="shop-detail__id">{{ shop.shopId }}</span>
          </NDescriptionsItem>
          <NDescriptionsItem label="状态">
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

      <section class="shop-detail__section">
        <h3>执行配置</h3>
        <NDescriptions :column="1" label-placement="left" bordered>
          <NDescriptionsItem label="主执行设备">
            {{ shop.executionDeviceName ?? '未分配' }}
          </NDescriptionsItem>
          <NDescriptionsItem label="主设备 ID">
            <span class="shop-detail__id">{{
              shop.executionDeviceId ?? '—'
            }}</span>
          </NDescriptionsItem>
          <NDescriptionsItem label="备用设备">
            {{ shop.backupDeviceNames.join('、') || '未分配' }}
          </NDescriptionsItem>
        </NDescriptions>
      </section>

      <section class="shop-detail__section">
        <h3>待接入能力</h3>
        <div class="shop-detail-placeholders">
          <article>
            <strong>账号与连接</strong>
            <span>账号、Cookie 与连接状态尚未接入</span>
          </article>
          <article>
            <strong>自动化</strong>
            <span>自动化配置与控制能力尚未接入</span>
          </article>
          <article>
            <strong>数据同步</strong>
            <span>业务数据同步能力尚未接入</span>
          </article>
        </div>
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

.shop-detail-placeholders {
  display: grid;
  gap: var(--space-2);
}

.shop-detail-placeholders article {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  background: var(--bg-subtle);
}

.shop-detail-placeholders strong {
  color: var(--text-secondary);
  font-size: var(--font-size-body);
}

.shop-detail-placeholders span {
  color: var(--text-tertiary);
  font-size: var(--font-size-secondary);
}
</style>
