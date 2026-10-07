<script setup lang="ts">
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NDescriptions, NDescriptionsItem } from 'naive-ui'
import { DetailDrawer, ErrorState, LoadingState } from '@/shared/components'
import type { SelectionService } from '../model/contracts'

const props = defineProps<{
  id: string | null
  service: SelectionService
  contextKey: string
}>()
defineEmits<{ close: [] }>()
const query = useQuery({
  queryKey: computed(() => ['selection-candidate', props.contextKey, props.id]),
  enabled: computed(() => !!props.id),
  queryFn: ({ queryKey }) => props.service.candidate(String(queryKey[2])),
  retry: false,
})
</script>

<template>
  <DetailDrawer
    :show="!!id"
    title="候选商品详情"
    size="md"
    @update:show="!$event && $emit('close')"
  >
    <LoadingState v-if="query.isPending.value" />
    <ErrorState
      v-else-if="query.isError.value"
      :description="query.error.value?.message"
      retryable
      @retry="query.refetch()"
    />
    <NDescriptions
      v-else-if="query.data.value"
      :column="1"
      label-placement="left"
      bordered
    >
      <NDescriptionsItem label="标题">{{
        query.data.value.title
      }}</NDescriptionsItem>
      <NDescriptionsItem label="商品ID">{{
        query.data.value.productId
      }}</NDescriptionsItem>
      <NDescriptionsItem label="来源">{{
        query.data.value.source
      }}</NDescriptionsItem>
      <NDescriptionsItem label="统计周期">{{
        query.data.value.statisticalPeriod
      }}</NDescriptionsItem>
      <NDescriptionsItem label="榜单排名">{{
        query.data.value.rank ?? '—'
      }}</NDescriptionsItem>
      <NDescriptionsItem label="首次上榜">{{
        query.data.value.firstListed === null
          ? '—'
          : query.data.value.firstListed
            ? '是'
            : '否'
      }}</NDescriptionsItem>
      <NDescriptionsItem label="短视频用户支付金额"
        >{{ query.data.value.userPaidAmountRange ?? '—'
        }}{{
          query.data.value.userPaidAmountRange &&
          !query.data.value.userPaidAmountUnit
            ? '（单位未确认）'
            : query.data.value.userPaidAmountUnit
        }}</NDescriptionsItem
      >
      <NDescriptionsItem label="点击次数">{{
        query.data.value.clicksRange ?? '—'
      }}</NDescriptionsItem>
      <NDescriptionsItem label="成交件数">{{
        query.data.value.soldUnitsRange ?? '—'
      }}</NDescriptionsItem>
      <NDescriptionsItem label="带货视频数">{{
        query.data.value.videoCountRange ?? '—'
      }}</NDescriptionsItem>
    </NDescriptions>
  </DetailDrawer>
</template>
