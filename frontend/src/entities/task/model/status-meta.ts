import type { StatusTone } from '@/shared/components/StatusTag.vue'

import type { TaskStatusDto } from '../api/contracts'

export const TASK_STATUS_META: Record<
  TaskStatusDto,
  { label: string; tone: StatusTone }
> = {
  pending: { label: '待执行', tone: 'warning' },
  running: { label: '执行中', tone: 'info' },
  success: { label: '成功', tone: 'success' },
  failed: { label: '失败', tone: 'error' },
  lost: { label: '丢失 / 中断', tone: 'warning' },
}
