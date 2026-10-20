<script setup lang="ts">
import { NDescriptions, NDescriptionsItem, NProgress } from 'naive-ui'
import { PlatformDisplay } from '@/entities/platform'
import { StatusTag } from '@/shared/components'
import { AppDialog } from '@/shared/ui'
import type { CollectionTask } from '../model/contracts'

defineProps<{ show: boolean; task: CollectionTask | null }>()
defineEmits<{ 'update:show': [value: boolean] }>()

const statusLabels = {
  queued: '排队中',
  processing: '处理中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
} as const
const statusTones = {
  queued: 'neutral',
  processing: 'info',
  completed: 'success',
  failed: 'error',
  cancelled: 'neutral',
} as const
const ingestionLabels = {
  'not-started': '未开始入库',
  processing: '入库处理中',
  ingested: '已入库',
  failed: '入库失败',
} as const
</script>

<template>
  <AppDialog
    :show="show"
    title="采集任务详情"
    size="md"
    positive-text="关闭"
    :show-negative="false"
    @update:show="$emit('update:show', $event)"
    @confirm="$emit('update:show', false)"
  >
    <NDescriptions v-if="task" bordered :column="2" label-placement="left">
      <NDescriptionsItem label="平台">
        <PlatformDisplay :code="task.platform" />
      </NDescriptionsItem>
      <NDescriptionsItem label="公开状态">
        <StatusTag
          :label="statusLabels[task.status]"
          :tone="statusTones[task.status]"
        />
      </NDescriptionsItem>
      <NDescriptionsItem label="任务编号">{{ task.id }}</NDescriptionsItem>
      <NDescriptionsItem label="商品 ID">
        {{ task.productId ?? '—' }}
      </NDescriptionsItem>
      <NDescriptionsItem label="提交内容" :span="2">
        {{ task.inputValue }}
      </NDescriptionsItem>
      <NDescriptionsItem label="接收回执">
        {{ task.receiptId ?? '尚未收到' }}
      </NDescriptionsItem>
      <NDescriptionsItem label="入库状态">
        {{ ingestionLabels[task.ingestionState] }}
      </NDescriptionsItem>
      <NDescriptionsItem label="处理进度" :span="2">
        <NProgress
          v-if="task.progress !== null"
          type="line"
          :percentage="task.progress"
          :show-indicator="true"
        />
        <span v-else>—</span>
      </NDescriptionsItem>
      <NDescriptionsItem v-if="task.errorMessage" label="失败原因" :span="2">
        {{ task.errorMessage }}
      </NDescriptionsItem>
      <NDescriptionsItem label="创建时间">{{
        task.createdAt
      }}</NDescriptionsItem>
      <NDescriptionsItem label="更新时间">{{
        task.updatedAt
      }}</NDescriptionsItem>
    </NDescriptions>
  </AppDialog>
</template>
