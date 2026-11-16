export type DeviceConnectionStatusDto = 'online' | 'offline'

export interface DeviceRuntimeReadDto {
  device_id: string
  worker_version: string
  connection_status: DeviceConnectionStatusDto
  last_seen_at: string
  started_at: string
  updated_at: string
}

export interface DeviceReadDto {
  device_id: string
  display_name: string
  enabled: boolean
  location: string | null
  note: string | null
  deleted_at: string | null
  worker_runtime: DeviceRuntimeReadDto | null
  created_at: string
  updated_at: string
}

export interface DeviceListRequest {
  page: number
  page_size: number
}

export type DeviceProviderCodeDto = 'yingdao'

export type YingdaoProviderStatusDto =
  | 'not_installed'
  | 'version_unsupported'
  | 'starting'
  | 'need_login'
  | 'interface_unreachable'
  | 'ready'

export interface ProviderApplicationInventoryReadDto {
  app_id: string
  app_name: string
  version_id: string | null
  updated_at: string | null
  app_type: string | null
  group_id: string | null
}

export interface YingdaoProviderInventoryReadDto {
  provider: 'yingdao'
  available: boolean
  status: YingdaoProviderStatusDto
  status_reason_code: string | null
  status_reason: string | null
  provider_version: string | null
  execution_available: boolean
  execution_version: string | null
  execution_unavailable_reason: string | null
  logged_in: boolean
  account_display: string | null
  account_type: string | null
  enterprise_account: boolean | null
  user_id: string | null
  applications: ProviderApplicationInventoryReadDto[]
  discovered_at: string
}

export interface DeviceProviderInventoryReadDto {
  device_id: string
  provider_code: DeviceProviderCodeDto
  available: boolean
  provider_version: string | null
  account_display: string | null
  account_type: string | null
  enterprise_account: boolean | null
  last_discovered_at: string
  inventory: YingdaoProviderInventoryReadDto
  updated_at: string
}

export type DeviceSkillRuntimeDto = 'python' | 'rpa' | 'discovery'
export type DeviceSkillClassificationDto = 'internal' | 'business' | null

export interface DeviceSkillCapabilityReadDto {
  device_id: string
  skill_id: string
  display_name: string
  runtime: DeviceSkillRuntimeDto
  provider: string | null
  version: string
  classification: DeviceSkillClassificationDto
  input_schema: Record<string, unknown> | null
  updated_at: string
}
