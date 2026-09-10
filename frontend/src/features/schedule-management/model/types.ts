export type ScheduleOccurrenceFilterMode = 'all' | 'today' | 'selected'

export interface ScheduleFilterViewModel {
  enabled: boolean | null
  deviceId: string | null
  search: string
  occurrenceMode: ScheduleOccurrenceFilterMode
  selectedOccurrenceDate: number | null
}
