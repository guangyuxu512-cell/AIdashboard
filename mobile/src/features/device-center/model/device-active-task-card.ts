import type { ActiveTaskSummaryReadDto, TaskListItem } from '@/entities/task'

export function mapDeviceActiveTaskToTaskListItem(
  task: ActiveTaskSummaryReadDto,
  deviceDisplayName: string,
): TaskListItem {
  return {
    taskId: task.task_id,
    targetDeviceId: task.target_device_id,
    deviceDisplayName,
    skillId: task.skill_id,
    skillDisplayName: null,
    executionName: task.execution_display_name,
    status: task.status,
    progress: null,
    currentMessage: null,
    startedAt: task.started_at,
    finishedAt: null,
    createdAt: task.created_at,
  }
}
