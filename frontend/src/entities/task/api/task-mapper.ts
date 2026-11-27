import dayjs from 'dayjs'

import { formatSkillName } from '@/entities/business-skill/model/display'

import type { TaskListItemViewModel } from '../model/types'
import type { TaskListItemReadDto } from './contracts'

export function mapTaskListItemDto(
  dto: TaskListItemReadDto,
): TaskListItemViewModel {
  const displayName = dto.execution_display_name.trim() || dto.skill_display_name?.trim()
  const executionName = formatSkillName(dto.skill_id, displayName)
  return {
    taskId: dto.task_id,
    deviceId: dto.target_device_id,
    deviceName: dto.device_display_name,
    skillId: dto.skill_id,
    executionName,
    status: dto.status,
    progressDisplay: dto.progress
      ? dto.progress.total === null
        ? String(dto.progress.current)
        : `${dto.progress.current} / ${dto.progress.total}`
      : '—',
    currentMessage: dto.current_message?.trim() || '—',
    startedAtDisplay: dto.started_at
      ? dayjs(dto.started_at).format('YYYY-MM-DD HH:mm:ss')
      : '—',
    createdAt: dto.created_at,
  }
}
