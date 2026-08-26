import type { TaskListItemReadDto } from '../api/contracts'
import type { TaskListItem, TaskListPage } from './types'

export function resolveExecutionName(value: {
  execution_display_name?: string | null
  skill_display_name?: string | null
  skill_id: string
}): string {
  return (
    value.execution_display_name?.trim() ||
    value.skill_display_name?.trim() ||
    value.skill_id
  )
}

export function mapTaskListItem(dto: TaskListItemReadDto): TaskListItem {
  return {
    taskId: dto.task_id,
    targetDeviceId: dto.target_device_id,
    deviceDisplayName: dto.device_display_name,
    skillId: dto.skill_id,
    executionName: resolveExecutionName(dto),
    status: dto.status,
    progress: dto.progress,
    currentMessage: dto.current_message,
    startedAt: dto.started_at,
    finishedAt: dto.finished_at,
    createdAt: dto.created_at,
  }
}

export function flattenTaskPages(pages: TaskListPage[]): TaskListItem[] {
  const seen = new Set<string>()
  const items: TaskListItem[] = []

  for (const page of pages) {
    for (const task of page.items) {
      if (seen.has(task.taskId)) continue
      seen.add(task.taskId)
      items.push(task)
    }
  }

  return items
}

export function mapTaskListPage(dto: {
  items: TaskListItemReadDto[]
  total: number
  page: number
  page_size: number
}): TaskListPage {
  return {
    items: dto.items.map(mapTaskListItem),
    total: dto.total,
    page: dto.page,
    pageSize: dto.page_size,
  }
}
