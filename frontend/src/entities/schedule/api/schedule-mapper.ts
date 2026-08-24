import type {
  ScheduleDetailViewModel,
  ScheduleListItemViewModel,
  ScheduleRunViewModel,
} from '../model/types'
import type {
  ScheduleListItemReadDto,
  ScheduleReadDto,
  ScheduleRunReadDto,
} from './contracts'

function formatInstant(value: string | null, timezone: string): string {
  if (!value) return '—'
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(new Date(value))
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((item) => item.type === type)?.value ?? ''
  return `${part('year')}-${part('month')}-${part('day')} ${part('hour')}:${part('minute')}`
}

export function normalizeLocalTime(value: string): string {
  return value.slice(0, 5)
}

export function mapScheduleRunDto(
  dto: ScheduleRunReadDto,
  timezone: string,
): ScheduleRunViewModel {
  return {
    runId: dto.run_id,
    scheduledFor: dto.scheduled_for,
    scheduledForDisplay: formatInstant(dto.scheduled_for, timezone),
    taskId: dto.task_id,
    taskStatus: dto.task_status,
    triggerResult: dto.trigger_result,
    triggerErrorCode: dto.trigger_error_code,
    triggerErrorMessage: dto.trigger_error_message,
  }
}

export function mapScheduleListItemDto(
  dto: ScheduleListItemReadDto,
): ScheduleListItemViewModel {
  const localTime = normalizeLocalTime(dto.local_time)
  return {
    scheduleId: dto.schedule_id,
    name: dto.name,
    enabled: dto.enabled,
    deviceId: dto.target_device_id,
    deviceName: dto.device_display_name,
    executionType: dto.execution_type,
    executionTypeDisplay:
      dto.execution_type === 'business_skill' ? '业务 Skill' : '影刀应用',
    skillId: dto.skill_id,
    executionName: dto.execution_display_name,
    scheduleType: dto.schedule_type,
    localTime,
    timezone: dto.timezone,
    triggerRuleDisplay: `每天 ${localTime}`,
    nextRunAt: dto.next_run_at,
    nextRunAtDisplay: formatInstant(dto.next_run_at, dto.timezone),
    latestRun: dto.latest_run
      ? mapScheduleRunDto(dto.latest_run, dto.timezone)
      : null,
    createdAt: dto.created_at,
    createdAtDisplay: formatInstant(dto.created_at, dto.timezone),
    updatedAt: dto.updated_at,
    updatedAtDisplay: formatInstant(dto.updated_at, dto.timezone),
  }
}

export function mapScheduleDetailDto(
  dto: ScheduleReadDto,
): ScheduleDetailViewModel {
  return {
    ...mapScheduleListItemDto(dto),
    applicationId: dto.application_id,
    parameters: { ...dto.parameters },
  }
}
