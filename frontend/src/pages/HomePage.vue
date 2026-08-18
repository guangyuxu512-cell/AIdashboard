<script setup lang="ts">
import { h, ref } from 'vue'
import type { DataTableColumns } from 'naive-ui'

import DataTable from '@/shared/components/DataTable.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import ErrorState from '@/shared/components/ErrorState.vue'
import FilterBar from '@/shared/components/FilterBar.vue'
import LoadingState from '@/shared/components/LoadingState.vue'
import PageHeader from '@/shared/components/PageHeader.vue'
import PageSection from '@/shared/components/PageSection.vue'
import PaginationBar from '@/shared/components/PaginationBar.vue'
import StatCard from '@/shared/components/StatCard.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import TableToolbar from '@/shared/components/TableToolbar.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppInput from '@/shared/ui/AppInput.vue'
import AppSelect from '@/shared/ui/AppSelect.vue'
import AppSwitch from '@/shared/ui/AppSwitch.vue'

interface FoundationRow {
  key: string
  layer: string
  responsibility: string
  status: 'ready'
}

const keyword = ref('')
const layer = ref<string | number | null>(null)
const enabled = ref(true)
const page = ref(1)
const pageSize = ref(10)

const layerOptions = [
  { label: 'Design Token', value: 'tokens' },
  { label: '基础 UI', value: 'ui' },
  { label: '页面模式', value: 'patterns' },
]

const rows: FoundationRow[] = [
  {
    key: 'tokens',
    layer: 'Design Token',
    responsibility: '颜色、排版、间距、尺寸与布局的唯一视觉来源',
    status: 'ready',
  },
  {
    key: 'ui',
    layer: '基础 UI',
    responsibility: '统一高频 Naive UI 控件的默认尺寸与行为',
    status: 'ready',
  },
  {
    key: 'patterns',
    layer: '页面模式',
    responsibility: '统一页面标题、筛选、工具栏、表格和状态布局',
    status: 'ready',
  },
]

const columns: DataTableColumns<FoundationRow> = [
  { title: '层级', key: 'layer', width: 160 },
  { title: '职责', key: 'responsibility' },
  {
    title: '状态',
    key: 'status',
    width: 120,
    render: () => h(StatusTag, { label: '已就绪', tone: 'success' }),
  },
]
</script>

<template>
  <div class="page-container">
    <PageHeader
      title="Frontend Design System"
      description="阶段 0B 只验证全局 UI 基础设施与桌面 AppShell，不包含真实业务。"
    >
      <template #actions>
        <AppButton>次要操作</AppButton>
        <AppButton tone="primary">主要操作</AppButton>
      </template>
    </PageHeader>

    <div class="stat-grid">
      <StatCard label="Design Token" value="1 套" description="CSS Token 为唯一视觉来源" tone="primary" />
      <StatCard label="基础控件" value="14 个" description="复用 Naive UI，不重复造轮子" tone="success" />
      <StatCard label="页面模式" value="16 个" description="覆盖骨架、状态与表格模式" />
    </div>

    <PageSection title="控件与页面模式" description="筛选与操作区域使用统一语义尺寸。">
      <FilterBar>
        <AppInput v-model="keyword" width="lg" clearable placeholder="搜索基础设施" />
        <AppSelect
          v-model="layer"
          width="md"
          clearable
          :options="layerOptions"
          placeholder="选择层级"
        />
        <AppSwitch v-model="enabled" />
        <template #actions>
          <AppButton tone="text">重置</AppButton>
          <AppButton tone="primary">查询</AppButton>
        </template>
      </FilterBar>

      <div class="table-pattern">
        <TableToolbar>
          <span class="selection-hint">已选择 0 项</span>
          <template #actions>
            <AppButton>刷新</AppButton>
            <AppButton tone="primary">新增占位</AppButton>
          </template>
        </TableToolbar>
        <DataTable :columns="columns" :data="rows" :row-key="(row) => row.key" />
        <PaginationBar
          v-model:page="page"
          v-model:page-size="pageSize"
          :item-count="rows.length"
        />
      </div>
    </PageSection>

    <PageSection title="统一状态" description="主要数据页面统一使用 Loading、Empty 与 Error 状态。">
      <div class="state-grid">
        <LoadingState description="加载状态示例" />
        <EmptyState description="空状态示例" />
        <ErrorState description="错误状态示例" />
      </div>
    </PageSection>
  </div>
</template>

<style scoped>
.stat-grid,
.state-grid {
  display: grid;
  gap: var(--layout-card-gap);
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.table-pattern {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  margin-top: var(--space-4);
}

.selection-hint {
  color: var(--color-text-secondary);
  font-size: var(--font-size-secondary);
}

.state-grid > * {
  border: 1px solid var(--color-border-default);
  border-radius: var(--radius-card);
  background: var(--color-bg-subtle);
}

@media (max-width: 1100px) {
  .stat-grid,
  .state-grid {
    grid-template-columns: 1fr;
  }
}
</style>
