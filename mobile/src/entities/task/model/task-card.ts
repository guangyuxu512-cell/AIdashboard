import type { MobileIconName } from '@/shared/icons'

import type { TaskStatusDto } from '../api/contracts'
import type { TaskListItem } from './types'

export type TaskArtworkState = 'running' | 'pending' | 'error' | 'done'

export interface TaskArtworkMeta {
  state: TaskArtworkState
  icon: MobileIconName
}

export function resolveTaskArtwork(status: TaskStatusDto): TaskArtworkMeta {
  switch (status) {
    case 'running':
      return { state: 'running', icon: 'running' }
    case 'pending':
      return { state: 'pending', icon: 'pending' }
    case 'failed':
    case 'lost':
      return { state: 'error', icon: 'failed' }
    case 'success':
      return { state: 'done', icon: 'success' }
  }
}

export function formatTaskDuration(
  task: Pick<TaskListItem, 'status' | 'startedAt' | 'finishedAt'>,
  now = new Date(),
): string | null {
  if (!task.startedAt) return null
  const start = new Date(task.startedAt)
  const end = task.finishedAt
    ? new Date(task.finishedAt)
    : task.status === 'running'
      ? now
      : null
  if (
    !end ||
    Number.isNaN(start.getTime()) ||
    Number.isNaN(end.getTime()) ||
    end <= start
  ) {
    return null
  }

  const totalMinutes = Math.floor((end.getTime() - start.getTime()) / 60_000)
  if (totalMinutes < 1) return '不足1分钟'
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours === 0) return `${minutes}分钟`
  return minutes === 0 ? `${hours}小时` : `${hours}小时${minutes}分钟`
}

export function getTaskCardTags(
  task: Pick<TaskListItem, 'skillDisplayName'>,
): string[] {
  const skillName = task.skillDisplayName?.trim()
  return skillName ? [skillName] : []
}
