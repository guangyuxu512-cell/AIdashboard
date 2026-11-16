<script setup lang="ts">
import {
  NDescriptions,
  NDescriptionsItem,
  NList,
  NListItem,
  NProgress,
  NText,
} from 'naive-ui'
import { PlatformDisplay } from '@/entities/platform'
import { StatusTag } from '@/shared/components'
import { AppButton, AppDialog } from '@/shared/ui'
import type { CollectionTask } from '../model/contracts'

defineProps<{ show: boolean; task: CollectionTask | null; busy?: boolean }>()
defineEmits<{
  'update:show': [value: boolean]
  'retry-item': [itemId: string]
  'recapture-item': [itemId: string]
}>()

const statusLabels = {
  pending: '排队中',
  running: '处理中',
  partial: '部分完成',
  succeeded: '已完成',
  failed: '失败',
  canceled: '已取消',
} as const
const statusTones = {
  pending: 'neutral',
  running: 'info',
  partial: 'warning',
  succeeded: 'success',
  failed: 'error',
  canceled: 'neutral',
} as const
const ingestionLabels = {
  'not-started': '未开始入库',
  processing: '入库处理中',
  ingested: '已入库',
  failed: '入库失败',
} as const
const itemStateLabels: Record<string, string> = {
  pending_dispatch: '等待派发',
  dispatching: '派发中',
  dispatched: '已派发',
  running: '采集中',
  received: '已接收',
  processing: '入库中',
  succeeded: '已完成',
  failed: '失败',
  canceled: '已取消',
}
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
        <PlatformDisplay v-if="task.platform" :code="task.platform" />
        <span v-else>多平台／明细加载后可见</span>
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
      <NDescriptionsItem label="明细统计" :span="2">
        共 {{ task.itemCount }} · 排队 {{ task.pendingCount }} · 处理中
        {{ task.runningCount }} · 成功 {{ task.succeededCount }} · 失败
        {{ task.failedCount }} · 取消 {{ task.canceledCount }}
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
    <NList v-if="task?.items?.length" bordered class="collection-task-items">
      <NListItem v-for="item in task.items" :key="item.id">
        <div class="collection-task-item">
          <div>
            <PlatformDisplay :code="item.platform" />
            <strong>{{ item.productId }}</strong>
            <NText depth="3">尝试 {{ item.attemptCount }} 次</NText>
          </div>
          <div>
            <StatusTag :label="itemStateLabels[item.state] ?? item.state" />
            <NText v-if="item.errorMessage" type="error">
              {{ item.errorMessage }}
            </NText>
          </div>
          <div class="collection-task-item__actions">
            <AppButton
              v-if="item.state === 'failed'"
              size="small"
              :disabled="busy"
              @click="$emit('retry-item', item.id)"
            >
              有限重试
            </AppButton>
            <AppButton
              v-if="
                item.collectionMode === 'auto_gateway' &&
                ['succeeded', 'failed', 'canceled'].includes(item.state)
              "
              size="small"
              :disabled="busy"
              @click="$emit('recapture-item', item.id)"
            >
              重新采集
            </AppButton>
          </div>
        </div>
      </NListItem>
    </NList>
  </AppDialog>
</template>

<style scoped>
.collection-task-items {
  margin-top: var(--space-4);
}
.collection-task-item,
.collection-task-item > div {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.collection-task-item {
  justify-content: space-between;
  min-width: 0;
}
.collection-task-item__actions {
  flex: 0 0 auto;
}
</style>
