<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { NTooltip } from 'naive-ui'
import { ShopMultiSelector } from '@/entities/shop'
import { AppButton, AppDialog } from '@/shared/ui'
import { StatusTag } from '@/shared/components'
import { productDataKeys } from '../api/query-keys'
import type {
  ProductDataCollectionBatch,
  ProductDataCollectionBatchCommand,
  ProductDataCollectionCommand,
  ProductDataSource,
} from '../model/types'

const props = defineProps<{
  source: ProductDataSource
  contextKey: string
  shopId: string | null
  period: ProductDataCollectionCommand['period'] | null
  enabled: boolean
}>()
const client = useQueryClient()
const visible = ref(false)
const selectedShopIds = ref<string[]>([])
const receipt = ref<ProductDataCollectionBatch | null>(null)
const intent = ref<ProductDataCollectionBatchCommand | null>(null)
const submissionInFlight = ref(false)
let revision = 0
const activeBatchStoragePrefix =
  'control-center.product-data.active-collection-batch.v1.'

function activeBatchStorageKey() {
  return `${activeBatchStoragePrefix}${props.contextKey}.${props.period ?? 'none'}`
}
function readActiveBatchId() {
  try {
    const value = window.localStorage.getItem(activeBatchStorageKey())
    return value &&
      /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
        value,
      )
      ? value
      : null
  } catch {
    return null
  }
}
function saveActiveBatchId(value: string | null) {
  try {
    if (value) window.localStorage.setItem(activeBatchStorageKey(), value)
    else window.localStorage.removeItem(activeBatchStorageKey())
  } catch {
    // Progress remains available for this page lifetime when storage is blocked.
  }
}
const activeBatchId = ref(readActiveBatchId())

const shops = useQuery({
  queryKey: computed(() => ['product-data-collection-shops', props.contextKey]),
  queryFn: () => props.source.collectionShops!(),
  enabled: computed(
    () => visible.value && !!props.source.collectionShops && props.enabled,
  ),
  retry: false,
})
const shopOptions = computed(() =>
  (shops.data.value ?? []).map((shop) => ({
    label: shop.shopName,
    value: shop.shopId,
  })),
)
const terminal = computed(
  () =>
    !!receipt.value &&
    ['succeeded', 'partial', 'failed'].includes(receipt.value.status),
)
const busy = computed(
  () =>
    !!receipt.value && ['pending', 'running'].includes(receipt.value.status),
)
const restoring = computed(() => !!activeBatchId.value && !receipt.value)

watch(
  () => [visible.value, shops.data.value] as const,
  ([show, available]) => {
    if (!show || !available || receipt.value) return
    const ids = new Set(available.map((shop) => shop.shopId))
    selectedShopIds.value =
      props.shopId && ids.has(props.shopId)
        ? [props.shopId]
        : available.map((shop) => shop.shopId)
  },
  { immediate: true },
)

const submit = useMutation({
  mutationFn: ({
    command,
    requestRevision,
  }: {
    command: ProductDataCollectionBatchCommand
    requestRevision: number
  }) => {
    void requestRevision
    return props.source.collectBatch!(command)
  },
  onSuccess(value, request) {
    if (request.requestRevision !== revision) return
    receipt.value = value
    activeBatchId.value = value.id
    saveActiveBatchId(value.id)
  },
  onSettled(_value, _error, request) {
    if (request.requestRevision === revision) submissionInFlight.value = false
  },
  retry: false,
})
const polling = useQuery({
  queryKey: computed(() => [
    'product-data-collection-batch',
    props.contextKey,
    activeBatchId.value,
  ]),
  queryFn: ({ queryKey }) => props.source.collectionBatch!(String(queryKey[2])),
  enabled: computed(
    () => !!props.source.collectionBatch && !!activeBatchId.value,
  ),
  refetchInterval: (query) =>
    !query.state.error &&
    query.state.data &&
    ['pending', 'running'].includes(query.state.data.status)
      ? 1000
      : false,
  retry: false,
})
watch(
  () => polling.data.value,
  (value) => {
    if (!value || value.id !== activeBatchId.value) return
    receipt.value = value
    if (['succeeded', 'partial', 'failed'].includes(value.status)) {
      saveActiveBatchId(null)
      activeBatchId.value = null
    }
    if (['succeeded', 'partial'].includes(value.status))
      void client.invalidateQueries({
        queryKey: productDataKeys.all(props.contextKey),
      })
  },
)
watch(
  () => [props.contextKey, props.period],
  () => {
    revision++
    visible.value = false
    selectedShopIds.value = []
    receipt.value = null
    activeBatchId.value = readActiveBatchId()
    intent.value = null
    submissionInFlight.value = false
    submit.reset()
  },
)

const reason = computed(() =>
  !props.enabled
    ? '当前环境未启用手动采集'
    : !props.period
      ? '仅支持近1/7/30天'
      : !props.source.collectBatch ||
          !props.source.collectionBatch ||
          !props.source.collectionShops
        ? '当前数据源未接入多店更新'
        : null,
)
const status = computed(() => {
  if (polling.error.value) return '回执读取未完成'
  if (restoring.value) return '读取采集进度'
  if (submit.error.value) return '提交未确认'
  if (!receipt.value) return null
  return {
    pending: '等待采集',
    running: '采集中',
    succeeded: '采集完成',
    partial: '部分完成',
    failed: '采集失败',
  }[receipt.value.status]
})
const summary = computed(() => {
  if (polling.error.value || submit.error.value) {
    const error = polling.error.value || submit.error.value
    return error instanceof Error ? error.message : '本次操作未完成'
  }
  const value = receipt.value
  return value
    ? `共 ${value.totalCount} 店；成功 ${value.succeededCount}；失败 ${value.failedCount}；执行中 ${value.runningCount}；排队 ${value.pendingCount}`
    : ''
})
const confirmDisabledReason = computed(() =>
  shops.error.value
    ? '可采集店铺读取失败'
    : selectedShopIds.value.length > 100
      ? '每次最多选择 100 家店铺'
      : !selectedShopIds.value.length
        ? '请至少选择一家店铺'
        : null,
)

function open() {
  if (reason.value) return
  if (polling.error.value && activeBatchId.value) {
    visible.value = true
    void polling.refetch()
    return
  }
  if (terminal.value) {
    receipt.value = null
    activeBatchId.value = null
    saveActiveBatchId(null)
    intent.value = null
    selectedShopIds.value = []
    submit.reset()
  }
  visible.value = true
}
function confirm() {
  if (
    submissionInFlight.value ||
    restoring.value ||
    busy.value ||
    confirmDisabledReason.value ||
    !props.period
  )
    return
  const shopIds = [...selectedShopIds.value].sort()
  if (
    !intent.value ||
    intent.value.period !== props.period ||
    intent.value.shopIds.join(',') !== shopIds.join(',')
  )
    intent.value = {
      shopIds,
      period: props.period,
      submissionKey: crypto.randomUUID(),
    }
  submissionInFlight.value = true
  submit.mutate({ command: intent.value, requestRevision: revision })
}
function itemStatus(item: ProductDataCollectionBatch['items'][number]) {
  const failures: Record<string, string> = {
    PRODUCT_DATA_COLLECTION_LIMIT_EXCEEDED: '超出采集上限',
    PRODUCT_DATA_SESSION_VALIDATION_REQUIRED: '需要重新登录',
    SHOP_SESSION_NOT_CONFIGURED: '需要登录店铺',
    SHOP_SESSION_PAYLOAD_INVALID: '会话数据无效',
    AUTH_INVALID: '登录已失效',
    PLATFORM_TIMEOUT: '平台请求超时',
  }
  return {
    pending: '排队中',
    running: `采集中 · ${item.generation.receivedPages} 页`,
    succeeded: `完成 · ${item.generation.receivedTotal ?? 0} 件`,
    failed: `失败 · ${
      (item.generation.failureCode && failures[item.generation.failureCode]) ??
      item.generation.failureCode ??
      '未知原因'
    }`,
  }[item.generation.status]
}
</script>

<template>
  <NTooltip v-if="status">
    <template #trigger><StatusTag :label="status" /></template>
    {{ summary }}
  </NTooltip>
  <NTooltip :disabled="!reason">
    <template #trigger>
      <span>
        <AppButton :disabled="!!reason" @click="open">
          {{
            polling.error.value
              ? '重新读取进度'
              : restoring
                ? '读取采集进度'
                : busy
                  ? '查看采集进度'
                  : '更新数据'
          }}
        </AppButton>
      </span>
    </template>
    {{ reason }}
  </NTooltip>

  <AppDialog
    v-model:show="visible"
    title="更新商品数据"
    size="md"
    :positive-text="restoring ? '读取中' : busy ? '采集中' : '提交更新'"
    :loading="submit.isPending.value"
    :positive-disabled="
      submissionInFlight || restoring || busy || !!confirmDisabledReason
    "
    :positive-disabled-reason="confirmDisabledReason"
    @confirm="confirm"
  >
    <div class="product-data-collection">
      <template v-if="polling.error.value">
        <div class="product-data-collection__empty">回执读取未完成，请重试</div>
      </template>
      <template v-else-if="restoring">
        <div class="product-data-collection__empty">正在恢复采集进度</div>
      </template>
      <template v-else-if="!receipt">
        <ShopMultiSelector
          v-if="shops.isFetching.value || shopOptions.length"
          v-model="selectedShopIds"
          :options="shopOptions"
          :loading="shops.isFetching.value"
        />
        <div
          v-else-if="!shops.error.value"
          class="product-data-collection__empty"
        >
          暂无可采集的授权抖店
        </div>
        <div class="product-data-collection__hint">
          已选择
          {{ selectedShopIds.length }} 家；任务提交后关闭客户端也会继续执行。
        </div>
      </template>
      <template v-else>
        <div class="product-data-collection__summary">{{ summary }}</div>
        <div class="product-data-collection__items">
          <div
            v-for="item in receipt.items"
            :key="item.shopId"
            class="product-data-collection__item"
          >
            <span :title="item.shopName">{{ item.shopName }}</span>
            <span>{{ itemStatus(item) }}</span>
          </div>
        </div>
      </template>
    </div>
  </AppDialog>
</template>

<style scoped>
.product-data-collection {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-3);
}
.product-data-collection__hint,
.product-data-collection__summary,
.product-data-collection__empty,
.product-data-collection__item span:last-child {
  color: var(--text-secondary);
  font-size: var(--font-size-secondary);
}
.product-data-collection__items {
  display: grid;
  gap: var(--space-2);
}
.product-data-collection__item {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-control);
}
.product-data-collection__item span:first-child {
  min-width: 0;
  overflow: hidden;
  color: var(--text-primary);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.product-data-collection__item span:last-child {
  flex: 0 0 auto;
}
</style>
