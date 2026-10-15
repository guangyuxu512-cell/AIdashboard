<script setup lang="ts">
// Browser-only contract fixture; not imported by the application or Real build.
import { computed, h, ref } from 'vue'
import {
  darkTheme,
  dateZhCN,
  NConfigProvider,
  NGlobalStyle,
  NMessageProvider,
  NTooltip,
  zhCN,
} from 'naive-ui'
import { createNaiveThemeOverrides } from '@/app/providers/naive-theme'
import { ProductImage, ProductInfoCell } from '@/entities/product'
import {
  DataTable,
  FilterBar,
  FilterField,
  ManagementListSection,
  PaginationBar,
  TableToolbar,
  ThemeSelector,
} from '@/shared/components'
import { AppButton, AppDrawer, AppInput, AppSelect } from '@/shared/ui'
import type { ListDensity } from '@/shared/ui'
import { useThemeStore } from '@/stores/theme'

const theme = useThemeStore()
theme.initialize()
const overrides = computed(() =>
  createNaiveThemeOverrides(theme.resolvedPreset),
)
const density = ref<ListDensity>('compact')
const selection = ref<string | null>('one')
const search = ref('')
const virtualSelection = ref<string | null>(null)
const virtualOptions = Array.from({ length: 80 }, (_, index) => ({
  label: `第 ${index + 1} 项可选类目`,
  value: String(index + 1),
}))
const page = ref(1)
const pageSize = ref(10)
const show = ref(false)
const options = [
  {
    label: '完整长店铺名称用于验证紧凑筛选下拉浮层和悬浮提示-甲',
    value: 'one',
  },
  {
    label: '完整长店铺名称用于验证紧凑筛选下拉浮层和悬浮提示-乙',
    value: 'two',
  },
]
const photo = '/src/features/product-selection/fixtures/photos/product-1.webp'
const rows = [
  {
    id: '90000000000000000012345678901234567890',
    title:
      '完整长标题保持单行省略并使用原始字符串复制商品ID且不影响其他默认消费者',
    image: photo,
  },
  { id: null, title: '无图无ID示例', image: null },
]
const columns = computed(() => [
  {
    title: '商品信息',
    key: 'id',
    width: 330,
    render: (row: (typeof rows)[number]) =>
      h(ProductInfoCell, {
        productId: row.id,
        title: row.title,
        imageUrl: row.image,
        density: density.value,
      }),
  },
  { title: '数值', key: 'zero', width: 100, render: () => '0' },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    render: () =>
      h(
        AppButton,
        {
          size: 'small',
          tone: 'link',
          onClick: () => {
            show.value = true
          },
        },
        () => '详情',
      ),
  },
])
</script>

<template>
  <NConfigProvider
    abstract
    :theme="theme.resolvedTheme === 'dark' ? darkTheme : null"
    :theme-overrides="overrides"
    :locale="zhCN"
    :date-locale="dateZhCN"
  >
    <NGlobalStyle />
    <NMessageProvider>
      <main class="density-fixture">
        <header class="density-fixture__header">
          <ThemeSelector />
          <AppButton
            data-testid="toggle-density"
            @click="density = density === 'compact' ? 'default' : 'compact'"
            >{{
              density === 'compact' ? '切换默认列表' : '切换紧凑列表'
            }}</AppButton
          >
          <AppButton data-testid="open-detail" @click="show = true"
            >打开默认详情</AppButton
          >
          <NTooltip
            ><template #trigger
              ><AppButton data-testid="default-tooltip"
                >默认提示</AppButton
              ></template
            >未启用紧凑的提示</NTooltip
          >
        </header>
        <FilterBar :density="density" data-testid="scoped-filter">
          <FilterField label="请求店铺"
            ><AppSelect
              v-model="selection"
              :options="options"
              clearable
              filterable
              label-tooltip
              to="#app-overlay-host"
              data-testid="scoped-select"
          /></FilterField>
          <FilterField label="搜索"
            ><AppInput v-model="search" data-testid="scoped-input"
          /></FilterField>
          <FilterField label="大列表"
            ><AppSelect
              v-model="virtualSelection"
              :options="virtualOptions"
              clearable
              filterable
              data-testid="virtual-select"
              to="#app-overlay-host"
          /></FilterField>
          <template #actions
            ><AppButton data-testid="scoped-reset">重置</AppButton></template
          >
          <template #primary-action
            ><AppButton tone="primary" data-testid="scoped-primary"
              >查询</AppButton
            ></template
          >
        </FilterBar>
        <ManagementListSection :density="density" data-testid="scoped-list">
          <TableToolbar :density="density"
            ><span>已选 1 项</span
            ><template #actions
              ><AppButton tone="primary" data-testid="batch"
                >批量采集资料</AppButton
              ></template
            ></TableToolbar
          >
          <DataTable :columns="columns" :data="rows" appearance="list" />
          <PaginationBar
            v-model:page="page"
            v-model:page-size="pageSize"
            :item-count="40"
            :density="density"
          />
        </ManagementListSection>
        <section data-testid="default-consumer">
          <AppInput
            model-value="其他表单保持默认"
            data-testid="default-input"
          />
          <AppSelect
            v-model="selection"
            :options="options"
            label-tooltip
            data-testid="default-select"
          />
          <ProductImage :src="photo" title="默认缩略图" size="thumbnail" />
        </section>
      </main>
      <!-- Siblings, not just Teleport targets, keep their original parent theme. -->
      <AppDrawer
        :show="show"
        title="默认详情"
        size="md"
        @update:show="show = $event"
      >
        <section data-testid="default-detail">
          <ProductImage :src="photo" title="默认摘要" />
          <ProductInfoCell
            :product-id="rows[0]!.id"
            :title="rows[0]!.title"
            :image-url="photo"
          />
          <AppInput model-value="详情表单仍为默认" />
        </section>
        <template #footer
          ><AppButton @click="show = false">关闭</AppButton></template
        >
      </AppDrawer>
      <div id="app-overlay-host" />
    </NMessageProvider>
  </NConfigProvider>
</template>

<style>
.density-fixture {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  min-height: 100%;
}
.density-fixture__header {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}
[data-testid='default-consumer'] {
  display: flex;
  gap: var(--space-3);
  align-items: center;
}
[data-testid='default-consumer'] > .app-field {
  max-width: var(--field-width-md);
}
</style>
