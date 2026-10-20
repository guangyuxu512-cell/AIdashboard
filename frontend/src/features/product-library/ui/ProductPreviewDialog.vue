<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  NDescriptions,
  NDescriptionsItem,
  NImage,
  NList,
  NListItem,
  NTabPane,
  NText,
  NTooltip,
  useMessage,
} from 'naive-ui'
import { ProductImage } from '@/entities/product'
import { PlatformDisplay } from '@/entities/platform'
import { ContextSwitchBar, StatusTag } from '@/shared/components'
import { AppButton, AppDialog, AppTabs } from '@/shared/ui'
import type { LibraryProduct } from '../model/contracts'

const props = defineProps<{ show: boolean; product: LibraryProduct | null }>()
defineEmits<{
  'update:show': [value: boolean]
  export: [product: LibraryProduct]
  group: [product: LibraryProduct]
}>()
const message = useMessage()
const gallery = ref<'main' | 'detail' | 'sku'>('main')
const selectedImage = ref<string | null>(null)
const imageFailed = ref(false)
const imageRevision = ref(0)
const detailTab = ref('sku')
const galleryItems = [
  { key: 'main', label: '主图' },
  { key: 'detail', label: '详情图' },
  { key: 'sku', label: 'SKU 图' },
]

const images = computed(() => {
  if (!props.product) return []
  if (gallery.value === 'detail') return props.product.detailImageUrls
  if (gallery.value === 'sku') return props.product.skuImageUrls
  return props.product.mainImageUrl ? [props.product.mainImageUrl] : []
})

watch(
  [() => props.show, () => props.product?.id, gallery],
  () => {
    selectedImage.value = images.value[0] ?? null
    imageFailed.value = false
  },
  { immediate: true },
)

function chooseImage(src: string) {
  selectedImage.value = src
  imageFailed.value = false
}

function setGallery(key: string) {
  gallery.value = key as typeof gallery.value
}

function retryImage() {
  imageFailed.value = false
  imageRevision.value += 1
}

async function copy(value: string, label: string) {
  try {
    await navigator.clipboard.writeText(value)
    message.success(`${label}已复制`)
  } catch {
    message.error('复制失败，请重试')
  }
}

const basicText = computed(() => {
  const row = props.product
  if (!row) return ''
  return [
    `商品标题：${row.title}`,
    `商品 ID：${row.productId}`,
    `来源平台：${row.platform}`,
    `完整类目：${row.category ?? '—'}`,
    `当前价格：${row.currentPrice === null ? '—' : `¥${row.currentPrice}`}`,
    `商品分组：${row.groupName ?? '未分组'}`,
    `采集时间：${row.collectedAt}`,
  ].join('\n')
})

const skuText = computed(() =>
  (props.product?.skus ?? [])
    .map(
      (sku) =>
        `${sku.name}\t${sku.id}\t${sku.currentPrice === null ? '—' : `¥${sku.currentPrice}`}\t${sku.stockLabel ?? '—'}`,
    )
    .join('\n'),
)

const allText = computed(() => {
  const row = props.product
  if (!row) return ''
  return [
    basicText.value,
    '',
    'SKU：',
    skuText.value,
    '',
    '属性：',
    ...row.attributes.map((item) => `${item.name}：${item.value}`),
  ].join('\n')
})
</script>

<template>
  <AppDialog
    :show="show"
    title="商品资料预览"
    size="lg"
    positive-text="关闭"
    :show-negative="false"
    @update:show="$emit('update:show', $event)"
    @confirm="$emit('update:show', false)"
  >
    <template v-if="product">
      <div class="product-preview__top-actions">
        <NTooltip>
          <template #trigger
            ><span><AppButton disabled>AI 改图</AppButton></span></template
          >
          AI 图片编辑尚未接入
        </NTooltip>
        <NTooltip>
          <template #trigger
            ><span><AppButton disabled>AI 审图</AppButton></span></template
          >
          AI 审图标准尚未接入
        </NTooltip>
      </div>

      <section class="product-preview__summary">
        <div class="product-preview__gallery">
          <ContextSwitchBar
            label="商品图片类型"
            appearance="bare"
            :items="galleryItems"
            :active-key="gallery"
            @select="setGallery"
          />
          <div class="product-preview__main-image">
            <NText v-if="!selectedImage" depth="3">—</NText>
            <AppButton v-else-if="imageFailed" tone="text" @click="retryImage">
              重试商品图片
            </AppButton>
            <NImage
              v-else
              :key="imageRevision"
              :src="selectedImage"
              :alt="product.title"
              object-fit="contain"
              :img-props="{ referrerpolicy: 'no-referrer' }"
              @error="imageFailed = true"
            />
          </div>
          <div class="product-preview__thumbnails">
            <button
              v-for="src in images"
              :key="src"
              type="button"
              class="product-preview__thumbnail"
              :class="{
                'product-preview__thumbnail--active': src === selectedImage,
              }"
              @click="chooseImage(src)"
            >
              <ProductImage
                :src="src"
                :title="product.title"
                size="thumbnail"
              />
            </button>
          </div>
        </div>

        <div class="product-preview__information">
          <h3>{{ product.title }}</h3>
          <NDescriptions bordered :column="1" label-placement="left">
            <NDescriptionsItem label="来源商品 ID">
              <span class="product-preview__inline-value">
                {{ product.productId }}
                <AppButton
                  size="small"
                  tone="link"
                  @click="copy(product.productId, '商品 ID')"
                >
                  复制
                </AppButton>
              </span>
            </NDescriptionsItem>
            <NDescriptionsItem label="来源平台">
              <PlatformDisplay :code="product.platform" />
            </NDescriptionsItem>
            <NDescriptionsItem label="当前价格">
              {{
                product.currentPrice === null ? '—' : `¥${product.currentPrice}`
              }}
            </NDescriptionsItem>
            <NDescriptionsItem label="商品分组">
              <span class="product-preview__inline-value">
                {{ product.groupName ?? '未分组' }}
                <AppButton size="small" @click="$emit('group', product)"
                  >移动分组</AppButton
                >
              </span>
            </NDescriptionsItem>
            <NDescriptionsItem label="采集时间">{{
              product.collectedAt
            }}</NDescriptionsItem>
          </NDescriptions>
          <div class="product-preview__copy-actions">
            <AppButton size="small" @click="copy(product.title, '商品标题')"
              >复制标题</AppButton
            >
            <AppButton size="small" @click="copy(basicText, '基础信息')"
              >复制基础信息</AppButton
            >
            <AppButton size="small" @click="copy(skuText, 'SKU 信息')"
              >复制 SKU</AppButton
            >
            <AppButton size="small" @click="copy(allText, '全部商品信息')"
              >复制全部信息</AppButton
            >
            <AppButton
              tone="primary"
              size="small"
              @click="$emit('export', product)"
            >
              导出 TXT
            </AppButton>
          </div>
        </div>
      </section>

      <AppTabs v-model="detailTab" type="line" class="product-preview__tabs">
        <NTabPane name="sku" tab="SKU">
          <NList bordered>
            <NListItem v-for="sku in product.skus" :key="sku.id">
              <div class="product-preview__sku">
                <ProductImage
                  :src="sku.imageUrl"
                  :title="sku.name"
                  size="thumbnail"
                />
                <div>
                  <strong>{{ sku.name }}</strong
                  ><br />{{ sku.id }}
                </div>
                <span>{{
                  sku.currentPrice === null ? '—' : `¥${sku.currentPrice}`
                }}</span>
                <span>{{ sku.stockLabel ?? '—' }}</span>
              </div>
            </NListItem>
          </NList>
        </NTabPane>
        <NTabPane name="attributes" tab="商品属性">
          <NDescriptions bordered :column="2">
            <NDescriptionsItem
              v-for="item in product.attributes"
              :key="item.name"
              :label="item.name"
            >
              {{ item.value }}
            </NDescriptionsItem>
          </NDescriptions>
        </NTabPane>
        <NTabPane name="images" tab="图片清单">
          <NList bordered>
            <NListItem
              v-for="(src, index) in [
                ...product.detailImageUrls,
                ...product.skuImageUrls,
              ]"
              :key="`${src}:${index}`"
            >
              图片 {{ index + 1 }} ·
              {{ src.startsWith('data:') ? '演示内存图片' : src }}
            </NListItem>
          </NList>
        </NTabPane>
        <NTabPane name="package" tab="资料包">
          <NList bordered>
            <NListItem v-for="file in product.packageFiles" :key="file.name">
              {{ file.name }}
              <template #suffix><StatusTag :label="file.kind" /></template>
            </NListItem>
          </NList>
        </NTabPane>
        <NTabPane name="history" tab="采集历史">
          <NList bordered>
            <NListItem v-for="item in product.history" :key="item.id">
              {{ item.collectedAt }} · {{ item.summary }}
              <template #suffix>
                <StatusTag
                  :label="
                    item.state === 'completed'
                      ? '完成'
                      : item.state === 'partial'
                        ? '部分完成'
                        : '失败'
                  "
                  :tone="
                    item.state === 'completed'
                      ? 'success'
                      : item.state === 'partial'
                        ? 'warning'
                        : 'error'
                  "
                />
              </template>
            </NListItem>
          </NList>
        </NTabPane>
      </AppTabs>
    </template>
  </AppDialog>
</template>

<style scoped>
.product-preview__top-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}
.product-preview__summary {
  display: grid;
  grid-template-columns: minmax(280px, 0.9fr) minmax(320px, 1.1fr);
  gap: var(--space-5);
}
.product-preview__gallery,
.product-preview__information {
  min-width: 0;
}
.product-preview__main-image {
  display: grid;
  min-height: 300px;
  margin: var(--space-3) 0;
  place-items: center;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  background: var(--bg-page);
}
.product-preview__main-image :deep(img) {
  width: 300px;
  max-width: 100%;
  height: 300px;
  object-fit: contain;
}
.product-preview__thumbnails,
.product-preview__copy-actions,
.product-preview__inline-value {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.product-preview__thumbnails {
  overflow-x: auto;
}
.product-preview__thumbnail {
  padding: var(--space-1);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  cursor: pointer;
}
.product-preview__thumbnail--active {
  border-color: var(--color-primary);
}
.product-preview__information h3 {
  margin: 0 0 var(--space-3);
  color: var(--text-primary);
  font-size: var(--font-size-page-title);
  font-weight: var(--font-weight-semibold);
}
.product-preview__copy-actions {
  flex-wrap: wrap;
  margin-top: var(--space-3);
}
.product-preview__tabs {
  margin-top: var(--space-5);
}
.product-preview__sku {
  display: grid;
  grid-template-columns: 72px minmax(180px, 1fr) 96px 120px;
  align-items: center;
  gap: var(--space-3);
}
@media (max-width: 820px) {
  .product-preview__summary {
    grid-template-columns: 1fr;
  }
  .product-preview__sku {
    grid-template-columns: 64px minmax(140px, 1fr);
  }
}
</style>
