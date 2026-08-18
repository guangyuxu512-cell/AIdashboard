<script setup lang="ts">
import { NDescriptions, NDescriptionsItem } from 'naive-ui'

import {
  SHOP_PLATFORM_META,
  ShopStatusTag,
  type ShopListItemViewModel,
} from '@/entities/shop'
import DetailDrawer from '@/shared/components/DetailDrawer.vue'
import AppButton from '@/shared/ui/AppButton.vue'

defineProps<{ show: boolean; shop: ShopListItemViewModel | null }>()

defineEmits<{ 'update:show': [value: boolean] }>()
</script>

<template>
  <DetailDrawer
    :show="show"
    title="店铺详情"
    size="md"
    @update:show="$emit('update:show', $event)"
  >
    <div v-if="shop" class="shop-detail">
      <section>
        <h3>基本信息</h3>
        <NDescriptions :column="1" label-placement="left" bordered>
          <NDescriptionsItem label="店铺名称">{{
            shop.shopName
          }}</NDescriptionsItem>
          <NDescriptionsItem label="平台">
            {{ SHOP_PLATFORM_META[shop.platform].label }}
          </NDescriptionsItem>
          <NDescriptionsItem label="负责人">{{
            shop.ownerName
          }}</NDescriptionsItem>
          <NDescriptionsItem label="店铺状态">
            <ShopStatusTag category="shop" :status="shop.operationalStatus" />
          </NDescriptionsItem>
          <NDescriptionsItem label="备注">{{
            shop.note || '—'
          }}</NDescriptionsItem>
        </NDescriptions>
      </section>

      <section>
        <h3>执行与配置状态</h3>
        <NDescriptions :column="1" label-placement="left" bordered>
          <NDescriptionsItem label="会话状态">
            <ShopStatusTag category="session" :status="shop.sessionStatus" />
          </NDescriptionsItem>
          <NDescriptionsItem label="执行设备">
            {{ shop.executionDeviceName ?? '未分配' }}
          </NDescriptionsItem>
          <NDescriptionsItem label="自动化状态">
            <ShopStatusTag
              category="automation"
              :status="shop.automationStatus"
            />
          </NDescriptionsItem>
          <NDescriptionsItem label="账号配置">
            <ShopStatusTag
              category="configuration"
              :status="shop.accountConfigurationStatus"
            />
          </NDescriptionsItem>
          <NDescriptionsItem label="会话配置">
            <ShopStatusTag
              category="configuration"
              :status="shop.sessionConfigurationStatus"
            />
          </NDescriptionsItem>
          <NDescriptionsItem label="更新时间">{{
            shop.updatedAtDisplay
          }}</NDescriptionsItem>
        </NDescriptions>
      </section>
    </div>

    <template #footer>
      <AppButton @click="$emit('update:show', false)">关闭</AppButton>
    </template>
  </DetailDrawer>
</template>

<style scoped>
.shop-detail {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.shop-detail section {
  min-width: 0;
}

.shop-detail h3 {
  margin-bottom: var(--space-3);
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
}
</style>
