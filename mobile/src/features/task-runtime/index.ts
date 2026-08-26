export {
  mergeTaskEvents,
  MOBILE_TASK_EVENT_LIMIT,
  MOBILE_TASK_EVENT_PAGE_SIZE,
} from './model/event-buffer'
export type { MergeTaskEventsResult } from './model/event-buffer'
export {
  deriveCurrentTaskMessage,
  deriveTaskProgress,
  formatTaskDateTime,
  formatTaskDuration,
  getRuntimeRetentionState,
  getTaskResultSummary,
  RUNTIME_RETENTION_TEXT,
} from './model/runtime-display'
export type { RuntimeRetentionState } from './model/runtime-display'
export {
  createExclusiveDrainController,
  drainTaskEventPages,
} from './model/runtime-drain'
export type {
  DrainTaskEventPagesOptions,
  ExclusiveDrainController,
  TaskEventDrainResult,
  TaskEventDrainStopReason,
} from './model/runtime-drain'
export {
  shouldPollTaskRuntime,
  TASK_RUNTIME_POLL_INTERVAL_MS,
  useTaskRuntime,
} from './model/use-task-runtime'
export {
  TASK_RUNTIME_CLOCK_INTERVAL_MS,
  useTaskRuntimeClock,
} from './model/use-task-runtime-clock'
export { default as TaskOutcomeNotice } from './ui/TaskOutcomeNotice.vue'
export { default as TaskRuntimeLog } from './ui/TaskRuntimeLog.vue'
