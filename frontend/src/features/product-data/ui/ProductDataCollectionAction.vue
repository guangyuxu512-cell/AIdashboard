<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { NTooltip } from 'naive-ui'
import { AppButton } from '@/shared/ui'
import { StatusTag } from '@/shared/components'
import { productDataKeys } from '../api/query-keys'
import type {
  ProductDataCollection,
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
const receipt = ref<ProductDataCollection | null>(null)
const intent = ref<ProductDataCollectionCommand | null>(null)
const submitting = ref(false)
let revision = 0
const submit = useMutation({
  mutationFn: ({
    command,
  }: {
    command: ProductDataCollectionCommand
    revision: number
  }) => props.source.collect!(command),
  onSuccess(value, request) {
    if (request.revision !== revision) return
    receipt.value = value
    if (value.status === 'succeeded')
      void client.invalidateQueries({
        queryKey: productDataKeys.all(props.contextKey),
      })
  },
  onSettled(_value, _error, request) {
    if (request.revision === revision) submitting.value = false
  },
  retry: false,
})
const polling = useQuery({
  queryKey: computed(() => [
    'product-data-collection',
    props.contextKey,
    receipt.value?.id,
  ]),
  queryFn: ({ queryKey }) => props.source.collection!(String(queryKey[2])),
  enabled: computed(
    () =>
      !!props.source.collection &&
      !!receipt.value &&
      ['pending', 'running'].includes(receipt.value.status) &&
      !receipt.value.leaseExpired,
  ),
  refetchInterval: (query) =>
    !query.state.error &&
    query.state.data &&
    ['pending', 'running'].includes(query.state.data.status) &&
    !query.state.data.leaseExpired
      ? 1000
      : false,
  retry: false,
})
watch(
  () => polling.data.value,
  (value) => {
    if (!value || value.id !== receipt.value?.id) return
    receipt.value = value
    if (value.status === 'succeeded')
      void client.invalidateQueries({
        queryKey: productDataKeys.all(props.contextKey),
      })
  },
)
watch(
  () => [props.contextKey, props.shopId, props.period],
  () => {
    revision++
    receipt.value = null
    intent.value = null
    submitting.value = false
    submit.reset()
  },
)
const busy = computed(
  () =>
    !!receipt.value &&
    ['pending', 'running'].includes(receipt.value.status) &&
    !receipt.value.leaseExpired,
)
const reason = computed(() =>
  !props.enabled
    ? '当前环境未启用手动采集'
    : !props.shopId
      ? '请先查询单个店铺'
      : !props.period
        ? '仅支持近1/7/30天'
        : null,
)
const disabled = computed(
  () =>
    !!reason.value || submitting.value || (busy.value && !polling.error.value),
)
const limitExceeded = computed(
  () =>
    receipt.value?.status === 'failed' &&
    receipt.value.failureCode === 'PRODUCT_DATA_COLLECTION_LIMIT_EXCEEDED',
)
const status = computed(() =>
  polling.error.value
    ? '回执读取未完成'
    : submit.error.value
      ? '提交未确认'
      : receipt.value?.leaseExpired
        ? '租约已到期'
        : receipt.value
          ? {
              pending: '采集中',
              running: '采集中',
              succeeded: '采集完成',
              failed: limitExceeded.value ? '超出采集上限' : '采集失败',
            }[receipt.value.status]
          : null,
)
const details = computed(() => {
  const error = polling.error.value || submit.error.value
  if (error) return error instanceof Error ? error.message : '本次操作未完成'
  const value = receipt.value
  if (value && limitExceeded.value)
    return `${value.startDate} ～ ${value.endDate}；${value.expectedTotal === null ? '平台返回数量' : `平台返回 ${value.expectedTotal} 件`}超出当前环境单次采集上限；本次未发布，已有成功数据保持不变。`
  return value
    ? `${value.startDate} ～ ${value.endDate}；${value.stage}；${value.receivedPages} 页；${value.receivedTotal ?? '未知'}/${value.expectedTotal ?? '未知'} 件${value.failureCode ? '；' + value.failureCode : ''}`
    : ''
})
function run() {
  if (disabled.value) return
  if (polling.error.value) {
    void polling.refetch()
    return
  }
  if (!props.shopId || !props.period || !props.source.collect) return
  if (
    !intent.value ||
    (receipt.value && (!busy.value || receipt.value.leaseExpired))
  )
    intent.value = {
      shopId: props.shopId,
      period: props.period,
      submissionKey: crypto.randomUUID(),
    }
  submitting.value = true
  submit.mutate({ command: intent.value, revision })
}
</script>

<template>
  <NTooltip v-if="status"
    ><template #trigger><StatusTag :label="status" /></template
    >{{ details }}</NTooltip
  >
  <NTooltip :disabled="!reason"
    ><template #trigger
      ><span
        ><AppButton
          :disabled="disabled"
          :loading="submit.isPending.value"
          @click="run"
          >{{
            polling.error.value
              ? '重新读取回执'
              : submit.error.value
                ? '重试提交'
                : '更新数据'
          }}</AppButton
        ></span
      ></template
    >{{ reason }}</NTooltip
  >
</template>
