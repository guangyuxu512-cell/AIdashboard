<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query'
import dayjs from 'dayjs'
import type { DataTableColumns } from 'naive-ui'
import { computed, h, ref, watch } from 'vue'

import { deviceApi, type SourcingAccountPresenceDto, type SourcingAgentPresenceDto } from '@/entities/device'
import DataTable from '@/shared/components/DataTable.vue'
import FilterBar from '@/shared/components/FilterBar.vue'
import ManagementListSection from '@/shared/components/ManagementListSection.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import { useAuthStore } from '@/stores/auth'

type Row = { key: string; agent: SourcingAgentPresenceDto; account: SourcingAccountPresenceDto | null }
const auth = useAuthStore()
const keyword = ref(''), page = ref(1), pageSize = ref(20)
const query = useQuery({
  queryKey: computed(() => ['devices', 'sourcing-account-overview', auth.currentUser?.userId]),
  queryFn: () => deviceApi.getSourcingOverview(), refetchInterval: 15_000,
})
const rows = computed<Row[]>(() => (query.data.value ?? []).flatMap<Row>((agent) => agent.accounts.length
  ? agent.accounts.map((account) => ({ key: `${agent.reporterId}:${account.accountId}`, agent, account }))
  : [{ key: `${agent.reporterId}:empty`, agent, account: null }]))
const filtered = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  return text ? rows.value.filter((row) => [row.agent.deviceName, row.account?.name].some((value) => value?.toLowerCase().includes(text))) : rows.value
})
watch([keyword, pageSize], () => { page.value = 1 })
watch(filtered, (items) => { page.value = Math.min(page.value, Math.max(1, Math.ceil(items.length / pageSize.value))) })
const visible = computed(() => filtered.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
const formatTime = (value: number | null) => value ? dayjs.unix(value).format('YYYY-MM-DD HH:mm:ss') : '—'
const session = (account: SourcingAccountPresenceDto | null) => {
  if (!account) return { label:'—', tone:'neutral' as const }
  if (account.sessionStatus === 'valid') {
    if (!account.sessionCheckedAt || Date.now() / 1000 - account.sessionCheckedAt > 30 * 60) return { label:'待复验', tone:'neutral' as const }
    return { label:'有效', tone:'success' as const }
  }
  if (account.sessionStatus === 'expired') return { label:'已失效', tone:'error' as const }
  if (account.sessionStatus === 'needs_verification') return { label:'需验证', tone:'warning' as const }
  return { label:'未确认', tone:'neutral' as const }
}
const columns: DataTableColumns<Row> = [
  { title:'设备', key:'device', minWidth:160, render:(row) => row.agent.deviceName },
  { title:'账号', key:'account', minWidth:160, render:(row) => row.account?.name || '—' },
  { title:'程序状态', key:'online', width:120, render:(row) => h(StatusTag, { label:row.agent.online ? '在线' : '离线', tone:row.agent.online ? 'success' : 'neutral' }) },
  { title:'会话状态', key:'session', width:120, render:(row) => h(StatusTag, session(row.account)) },
  { title:'会话验证时间', key:'checked', minWidth:170, render:(row) => formatTime(row.account?.sessionCheckedAt ?? null) },
  { title:'工作状态', key:'work', width:120, render:(row) => !row.agent.online || !row.account ? '—' : row.account.workStatus === 'working' ? '工作中' : '空闲' },
  { title:'程序版本', key:'version', width:120, render:(row) => row.agent.appVersion },
  { title:'最近上报', key:'seen', minWidth:170, render:(row) => formatTime(row.agent.lastSeenAt) },
]
</script>

<template>
  <div class="sourcing-accounts-section">
    <FilterBar>
      <AppInput v-model="keyword" width="md" clearable placeholder="搜索账号或设备" />
      <template #actions><AppButton :loading="query.isFetching.value" @click="query.refetch()">刷新</AppButton></template>
    </FilterBar>
    <ManagementListSection>
      <DataTable :columns="columns" :data="visible" :loading="query.isLoading.value" :error="query.error.value ? '加载失败' : null"
        :row-key="(row) => (row as Row).key" :scroll-x="1100" show-header-when-empty empty-description="暂无 1688 账号"
        viewport="fill" @retry="query.refetch()" />
      <PaginationBar v-model:page="page" v-model:page-size="pageSize" :item-count="filtered.length" />
    </ManagementListSection>
  </div>
</template>

<style scoped>
.sourcing-accounts-section { display:flex; min-height:0; flex:1; flex-direction:column; gap:var(--space-4); }
</style>
