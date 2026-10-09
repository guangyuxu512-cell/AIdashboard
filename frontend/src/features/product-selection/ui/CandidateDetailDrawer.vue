<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { Copy } from '@lucide/vue'
import { NDescriptions, NDescriptionsItem, NText, useMessage } from 'naive-ui'
import {
  DetailDrawer,
  ErrorState,
  LoadingState,
  StatusTag,
} from '@/shared/components'
import { AppButton } from '@/shared/ui'
import type { SelectionService } from '../model/contracts'
import {
  formatCandidateDate,
  formatCandidateTime,
  formatReviewRate,
  comparablePreviousRank,
  rankChangeLabel,
  collectionLabels,
  discoveryLabels,
  sourceProductUrl,
} from '../model/candidate-display'
import ExternalProductImage from './ExternalProductImage.vue'

const props = defineProps<{
  id: string | null
  service: SelectionService
  contextKey: string
}>()
const emit = defineEmits<{ close: []; updated: [] }>()
const message = useMessage()
const busy = ref(false)
const query = useQuery({
  queryKey: computed(() => ['selection-candidate', props.contextKey, props.id]),
  enabled: computed(() => !!props.id),
  queryFn: ({ queryKey }) => props.service.candidate(String(queryKey[2])),
  retry: false,
})
const row = computed(() => query.data.value)
const sourceUrl = computed(() => sourceProductUrl(row.value?.sourceUrl ?? null))
async function copyProductId() {
  if (!row.value) return
  try {
    await navigator.clipboard.writeText(row.value.productId)
    message.success('商品ID已复制')
  } catch {
    message.error('商品ID复制失败')
  }
}
async function act(action: 'collect' | 'metrics' | 'competitor') {
  if (busy.value || !row.value) return
  const id = row.value.id
  const contextKey = props.contextKey
  const merchantShopId = row.value.merchant?.shopId
  if (action === 'competitor' && !merchantShopId) {
    message.error('商品商家身份缺失，无法标记竞品店铺')
    return
  }
  busy.value = true
  try {
    const receipt =
      action === 'collect'
        ? await props.service.demoAction(id, 'collect')
        : action === 'metrics'
          ? await props.service.updateCompassMetrics(id)
          : await props.service.markCompetitor(merchantShopId!)
    if (props.id !== id || props.contextKey !== contextKey) return
    message.info(receipt.message)
    await query.refetch()
    emit('updated')
  } catch (error) {
    if (props.id === id && props.contextKey === contextKey)
      message.error(error instanceof Error ? error.message : '操作失败，请重试')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <DetailDrawer
    :show="!!id"
    title="候选商品详情"
    size="md"
    @update:show="!$event && emit('close')"
  >
    <LoadingState v-if="query.isPending.value" />
    <ErrorState
      v-else-if="query.isError.value"
      :description="query.error.value?.message"
      retryable
      @retry="query.refetch()"
    />
    <div v-else-if="row" class="candidate-detail">
      <div class="candidate-detail__summary">
        <ExternalProductImage :src="row.imageUrl" :title="row.title" />
        <div class="candidate-detail__identity">
          <strong>{{ row.title }}</strong>
          <NText :depth="row.priceBand === null ? 3 : undefined"
            >价格／价格带：{{ row.priceBand ?? '—' }}</NText
          >
        </div>
      </div>
      <section>
        <NDescriptions :column="1" label-placement="left" bordered>
          <NDescriptionsItem label="商品ID">
            <div class="candidate-detail__inline">
              <span>{{ row.productId }}</span>
              <AppButton
                tone="text"
                :aria-label="`复制商品ID ${row.productId}`"
                @click="copyProductId"
                ><Copy :size="16" aria-hidden="true"
              /></AppButton>
              <AppButton
                v-if="sourceUrl"
                tone="link"
                tag="a"
                :href="sourceUrl"
                target="_blank"
                rel="noopener noreferrer"
                >查看源商品</AppButton
              >
            </div>
          </NDescriptionsItem>
          <NDescriptionsItem label="商品所属商家">
            <div class="candidate-detail__inline">
              <NText :depth="row.merchant ? undefined : 3">{{
                row.merchant?.name ?? '—'
              }}</NText>
              <AppButton
                tone="secondary"
                :disabled="
                  busy || !row.merchant?.shopId || row.merchant.competitor
                "
                @click="act('competitor')"
                >{{
                  row.merchant?.competitor ? '已标记竞品店铺' : '标记为竞品店铺'
                }}</AppButton
              >
            </div>
            <NText v-if="!row.merchant?.shopId" tag="div" depth="3"
              >商品商家身份未确认</NText
            >
          </NDescriptionsItem>
          <NDescriptionsItem label="请求罗盘使用的自有店铺"
            ><NText depth="2">{{ row.shopName }}</NText></NDescriptionsItem
          >
          <NDescriptionsItem label="完整类目">{{
            row.category
          }}</NDescriptionsItem>
          <NDescriptionsItem label="来源">{{ row.source }}</NDescriptionsItem>
          <NDescriptionsItem label="所属榜单">{{
            row.sourceContext.leaderboardName
          }}</NDescriptionsItem>
          <NDescriptionsItem label="本次排名"
            ><NText :depth="row.rank === null ? 3 : undefined">{{
              row.rank ?? '—'
            }}</NText
            ><NText v-if="rankChangeLabel(row)" depth="3">
              · {{ rankChangeLabel(row) }}</NText
            ></NDescriptionsItem
          >
          <NDescriptionsItem label="上次排名"
            ><NText :depth="row.previousRank === null ? 3 : undefined">{{
              row.previousRank?.rank ?? '—'
            }}</NText
            ><NText
              v-if="row.previousRank && comparablePreviousRank(row) === null"
              depth="3"
              >（口径不同，不作比较）</NText
            ></NDescriptionsItem
          >
          <NDescriptionsItem label="发现情况"
            ><NText :depth="row.discovery === 'unknown' ? 3 : undefined">{{
              discoveryLabels[row.discovery]
            }}</NText></NDescriptionsItem
          >
          <NDescriptionsItem label="平台首次上榜"
            ><NText :depth="row.firstListed === null ? 3 : undefined">{{
              row.firstListed === null ? '—' : row.firstListed ? '是' : '否'
            }}</NText></NDescriptionsItem
          >
          <NDescriptionsItem label="首次发现时间">{{
            formatCandidateTime(row.firstDiscoveredAt)
          }}</NDescriptionsItem>
          <NDescriptionsItem label="差评率"
            ><NText :depth="row.negativeReviewRate === null ? 3 : undefined">{{
              formatReviewRate(row.negativeReviewRate)
            }}</NText></NDescriptionsItem
          >
          <NDescriptionsItem label="首次上架日期"
            ><NText :depth="row.listedAt === null ? 3 : undefined">{{
              formatCandidateDate(row.listedAt)
            }}</NText></NDescriptionsItem
          >
          <NDescriptionsItem label="指标获取时间">{{
            formatCandidateTime(row.metricsRetrievedAt)
          }}</NDescriptionsItem>
          <NDescriptionsItem label="商品资料采集状态"
            ><StatusTag
              :label="collectionLabels[row.collectionStatus]"
              :tone="row.collectionStatus === 'failed' ? 'error' : 'neutral'"
          /></NDescriptionsItem>
          <NDescriptionsItem label="屏蔽状态">{{
            row.blocked ? '已屏蔽' : '未屏蔽'
          }}</NDescriptionsItem>
        </NDescriptions>
      </section>
      <section>
        <h3>罗盘视频榜单数据</h3>
        <NText tag="div" depth="3"
          >统计周期：{{ row.sourceContext.statisticalPeriod }} · 获取时间：{{
            formatCandidateTime(row.metricsRetrievedAt)
          }}</NText
        >
        <NDescriptions :column="1" label-placement="left" bordered>
          <NDescriptionsItem label="短视频用户支付金额"
            ><NText :depth="row.userPaidAmountRange === null ? 3 : undefined">{{
              row.userPaidAmountRange ?? '—'
            }}</NText
            ><NText
              v-if="row.userPaidAmountRange && !row.userPaidAmountUnit"
              depth="3"
              >（单位未确认）</NText
            ><template v-else>{{
              row.userPaidAmountUnit
            }}</template></NDescriptionsItem
          >
          <NDescriptionsItem label="短视频点击次数"
            ><NText :depth="row.clicksRange === null ? 3 : undefined">{{
              row.clicksRange ?? '—'
            }}</NText></NDescriptionsItem
          >
          <NDescriptionsItem label="短视频成交件数"
            ><NText :depth="row.soldUnitsRange === null ? 3 : undefined">{{
              row.soldUnitsRange ?? '—'
            }}</NText></NDescriptionsItem
          >
          <NDescriptionsItem label="带货视频数"
            ><NText :depth="row.videoCountRange === null ? 3 : undefined">{{
              row.videoCountRange ?? '—'
            }}</NText></NDescriptionsItem
          >
        </NDescriptions>
      </section>
    </div>
    <template #footer>
      <div class="candidate-detail__actions">
        <AppButton @click="emit('close')">关闭</AppButton>
        <AppButton
          tone="secondary"
          :disabled="!row || busy || !service.available"
          @click="act('metrics')"
          >更新罗盘指标</AppButton
        >
        <AppButton
          tone="primary"
          :disabled="!row || busy || !service.available"
          :loading="busy"
          @click="act('collect')"
          >采集资料</AppButton
        >
      </div>
    </template>
  </DetailDrawer>
</template>

<style scoped>
.candidate-detail {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  min-width: 0;
}
.candidate-detail__summary,
.candidate-detail__inline,
.candidate-detail__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.candidate-detail__inline {
  flex-wrap: wrap;
  overflow-wrap: anywhere;
}
.candidate-detail__summary > :first-child {
  flex-shrink: 0;
}
.candidate-detail__identity {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
}
.candidate-detail__identity strong {
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
  overflow-wrap: anywhere;
}
.candidate-detail h3 {
  font-size: var(--font-size-section-title);
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-3);
}
.candidate-detail__actions {
  justify-content: flex-end;
  flex-wrap: wrap;
}
</style>
