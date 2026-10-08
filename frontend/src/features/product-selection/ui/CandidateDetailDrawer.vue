<script setup lang="ts">
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { NDescriptions, NDescriptionsItem, NText } from 'naive-ui'
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
      <NDescriptionsItem label="榜单排名"
        ><NText :depth="query.data.value.rank === null ? 3 : undefined">{{
          query.data.value.rank ?? '—'
        }}</NText></NDescriptionsItem
      >
      <NDescriptionsItem label="首次上榜"
        ><NText
          :depth="query.data.value.firstListed === null ? 3 : undefined"
          >{{
            query.data.value.firstListed === null
              ? '—'
              : query.data.value.firstListed
                ? '是'
                : '否'
          }}</NText
        ></NDescriptionsItem
      >
      <NDescriptionsItem label="短视频用户支付金额"
        ><NText
          :depth="query.data.value.userPaidAmountRange === null ? 3 : undefined"
          >{{ query.data.value.userPaidAmountRange ?? '—' }}</NText
        >
        <NText
          v-if="
            query.data.value.userPaidAmountRange &&
            !query.data.value.userPaidAmountUnit
          "
          :depth="3"
          >（单位未确认）</NText
        >
        <template v-else>{{
          query.data.value.userPaidAmountUnit
        }}</template></NDescriptionsItem
      >
      <NDescriptionsItem label="点击次数"
        ><NText
          :depth="query.data.value.clicksRange === null ? 3 : undefined"
          >{{ query.data.value.clicksRange ?? '—' }}</NText
        ></NDescriptionsItem
      >
      <NDescriptionsItem label="成交件数"
        ><NText
          :depth="query.data.value.soldUnitsRange === null ? 3 : undefined"
          >{{ query.data.value.soldUnitsRange ?? '—' }}</NText
        ></NDescriptionsItem
      >
      <NDescriptionsItem label="带货视频数"
        ><NText
          :depth="query.data.value.videoCountRange === null ? 3 : undefined"
          >{{ query.data.value.videoCountRange ?? '—' }}</NText
        ></NDescriptionsItem
      >
    </NDescriptions>
  </DetailDrawer>
</template>
