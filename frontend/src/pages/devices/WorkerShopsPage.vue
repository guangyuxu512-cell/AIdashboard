<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query'
import dayjs from 'dayjs'
import { NTab, type DataTableColumns } from 'naive-ui'
import { computed, h, ref, watch } from 'vue'

import { deviceApi, workerShopSessionStatusMeta, type DeviceLocalShopDto, type DeviceShopOverviewDto } from '@/entities/device'
import DataTable from '@/shared/components/DataTable.vue'
import FilterBar from '@/shared/components/FilterBar.vue'
import ManagementListSection from '@/shared/components/ManagementListSection.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import AppTabs from '@/shared/ui/AppTabs.vue'
import { useAuthStore } from '@/stores/auth'
import SourcingAccountsSection from './SourcingAccountsSection.vue'

type SessionStatus = DeviceLocalShopDto['session_status']
type ShopRow = DeviceLocalShopDto & { device: DeviceShopOverviewDto; rowKey: string }

const auth = useAuthStore()
const tab = ref('shops')
watch(() => auth.isSuperAccount, (allowed) => { if (!allowed) tab.value = 'shops' })
const keyword = ref('')
const page = ref(1)
const pageSize = ref(20)
const query = useQuery({
  queryKey: computed(() => ['devices', 'shop-overview', auth.currentUser?.userId, auth.activeTeamId]),
  queryFn: () => deviceApi.getShopOverview(),
  refetchInterval: 60_000,
})
const rows = computed(() => (query.data.value ?? []).flatMap((device) =>
  device.shops.map((shop) => ({ ...shop, device, rowKey: `${device.device_id}:${shop.local_shop_id}` })),
))
const filtered = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  return text ? rows.value.filter((row) => [row.shop_name, row.platform_shop_id, row.device.device_name]
    .some((value) => value?.toLowerCase().includes(text))) : rows.value
})
watch([keyword, () => auth.activeTeamId, pageSize], () => { page.value = 1 })
watch(filtered, (items) => { page.value = Math.min(page.value, Math.max(1, Math.ceil(items.length / pageSize.value))) })
const visibleRows = computed(() => filtered.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))

const statusCell = (status: SessionStatus, checkedAt?: string | null) =>
  h(StatusTag, workerShopSessionStatusMeta(status, checkedAt))
const formatTime = (value?: string | null) => value && dayjs(value).isValid()
  ? dayjs(value).format('YYYY-MM-DD HH:mm:ss') : '—'
const columns: DataTableColumns<ShopRow> = [
  { title: '店铺', key: 'shop_name', minWidth: 160 },
  { title: '平台店铺 ID', key: 'platform_shop_id', minWidth: 160,
    render: (row) => row.platform_shop_id || '—' },
  { title: 'Worker 设备', key: 'device', minWidth: 160, render: (row) => row.device.device_name },
  { title: '设备状态', key: 'online', width: 120, render: (row) => {
    const online = row.device.device_enabled && row.device.worker_runtime?.connection_status === 'online' && row.device.available
    return h(StatusTag, { label: online ? '在线' : '不可用', tone: online ? 'success' : 'neutral' })
  } },
  { title: '抖店', key: 'session_status', width: 110,
    render: (row) => row.platform === 'douyin' ? statusCell(row.session_status, row.status_observed_at) : '—' },
  { title: '抖店验证时间', key: 'status_observed_at', minWidth: 170,
    render: (row) => row.platform !== 'douyin' || row.session_status === 'reauthorization_required'
      ? '—' : formatTime(row.status_observed_at) },
  { title: '罗盘', key: 'compass_session_status', width: 110,
    render: (row) => row.platform === 'douyin' ? statusCell(row.compass_session_status ?? 'unknown', row.compass_status_observed_at) : '—' },
  { title: '罗盘验证时间', key: 'compass_status_observed_at', minWidth: 170,
    render: (row) => row.platform === 'douyin' ? formatTime(row.compass_status_observed_at) : '—' },
]
</script>

<template>
  <div class="page-container worker-shops-page">
    <AppTabs v-if="auth.isSuperAccount" v-model="tab">
      <NTab name="shops">抖店</NTab><NTab name="sourcing">1688 账号</NTab>
    </AppTabs>
    <template v-if="tab === 'shops'">
    <FilterBar>
      <AppInput v-model="keyword" width="md" clearable placeholder="搜索店铺或设备" />
      <template #actions>
        <AppButton :loading="query.isFetching.value" @click="query.refetch()">刷新</AppButton>
      </template>
    </FilterBar>
    <ManagementListSection>
      <DataTable :columns="columns" :data="visibleRows" :loading="query.isLoading.value"
        :error="query.error.value ? '加载失败' : null" :row-key="(row) => (row as ShopRow).rowKey"
        :scroll-x="1200" show-header-when-empty empty-description="暂无店铺映射"
        viewport="fill" @retry="query.refetch()" />
      <PaginationBar v-model:page="page" v-model:page-size="pageSize" :item-count="filtered.length" />
    </ManagementListSection>
    </template>
    <SourcingAccountsSection v-else-if="auth.isSuperAccount" />
  </div>
</template>

<style scoped>
.worker-shops-page { display: flex; height: 100%; min-height: 0; flex-direction: column; gap: var(--space-4); }
</style>
