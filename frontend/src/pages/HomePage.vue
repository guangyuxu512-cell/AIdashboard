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
import SummaryGrid from '@/shared/components/SummaryGrid.vue'
import TableToolbar from '@/shared/components/TableToolbar.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import AppDatePicker from '@/shared/ui/AppDatePicker.vue'
import AppDialog from '@/shared/ui/AppDialog.vue'
import AppDrawer from '@/shared/ui/AppDrawer.vue'
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
const selectedDate = ref<number | null>(null)
const page = ref(1)
const pageSize = ref(10)
const dialogVisible = ref(false)
const drawerVisible = ref(false)

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
      title="Design System Playground"
      description="Design Token V2 开发预览，用于验证主题、控件、表格与弹层的全局一致性。"
    >
      <template #actions>
        <AppButton @click="drawerVisible = true">打开 Drawer</AppButton>
        <AppButton tone="primary" @click="dialogVisible = true"
          >打开 Dialog</AppButton
        >
      </template>
    </PageHeader>

    <SummaryGrid :columns="3">
      <StatCard
        label="Design Token"
        value="V2"
        description="Light / Dark 语义 Token"
        tone="primary"
      />
      <StatCard
        label="基础控件"
        value="14 个"
        description="34px 默认密度"
        tone="success"
      />
      <StatCard
        label="页面模式"
        value="18 个"
        description="桌面工具型统一骨架"
      />
    </SummaryGrid>

    <PageSection
      title="控件与页面模式"
      description="筛选与操作区域使用统一语义尺寸。"
    >
      <FilterBar>
        <AppInput
          v-model="keyword"
          width="lg"
          clearable
          placeholder="搜索基础设施"
        />
        <AppSelect
          v-model="layer"
          width="md"
          clearable
          :options="layerOptions"
          placeholder="选择层级"
        />
        <AppDatePicker v-model="selectedDate" width="md" />
        <AppSwitch v-model="enabled" />
        <template #actions>
          <AppButton tone="text">重置</AppButton>
          <AppButton tone="primary">查询</AppButton>
        </template>
      </FilterBar>

      <div class="control-preview" aria-label="按钮与状态预览">
        <div>
          <AppButton tone="primary">Primary</AppButton>
          <AppButton>Secondary</AppButton>
          <AppButton tone="danger">Danger</AppButton>
          <AppButton disabled>Disabled</AppButton>
        </div>
        <div>
          <StatusTag label="信息" tone="info" />
          <StatusTag label="正常" tone="success" />
          <StatusTag label="警告" tone="warning" />
          <StatusTag label="异常" tone="error" />
          <StatusTag label="未接入" />
        </div>
      </div>

      <div class="table-pattern">
        <TableToolbar>
          <span class="selection-hint">已选择 0 项</span>
          <template #actions>
            <AppButton>刷新</AppButton>
            <AppButton tone="primary">新增占位</AppButton>
          </template>
        </TableToolbar>
        <DataTable
          :columns="columns"
          :data="rows"
          :row-key="(row) => row.key"
        />
        <PaginationBar
          v-model:page="page"
          v-model:page-size="pageSize"
          :item-count="rows.length"
        />
      </div>
    </PageSection>

    <PageSection
      title="统一状态"
      description="主要数据页面统一使用 Loading、Empty 与 Error 状态。"
    >
      <div class="state-grid">
        <LoadingState description="加载状态示例" />
        <EmptyState description="空状态示例" />
        <ErrorState description="错误状态示例" />
      </div>
    </PageSection>

    <AppDialog
      v-model:show="dialogVisible"
      title="Dialog 主题验收"
      positive-text="确认"
      @confirm="dialogVisible = false"
    >
      <p class="overlay-preview-copy">
        用于验收 Surface、Border、Shadow 与主题对比度。
      </p>
    </AppDialog>

    <AppDrawer v-model:show="drawerVisible" title="Drawer 主题验收" size="sm">
      <p class="overlay-preview-copy">Drawer 复用统一语义表面与紧凑内边距。</p>
      <template #footer>
        <AppButton @click="drawerVisible = false">关闭</AppButton>
      </template>
    </AppDrawer>
  </div>
</template>

<style scoped>
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

.control-preview,
.control-preview > div {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.control-preview {
  justify-content: space-between;
  margin-top: var(--space-3);
  flex-wrap: wrap;
}

.overlay-preview-copy {
  color: var(--text-secondary);
}

.selection-hint {
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}

.state-grid > * {
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  background: var(--bg-subtle);
}

@media (max-width: 1100px) {
  .state-grid {
    grid-template-columns: 1fr;
  }
}
</style>
