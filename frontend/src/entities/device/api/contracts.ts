export interface DeviceRuntimeReadDto {
  device_id: string
  worker_version: string
  connection_status: 'online' | 'offline'
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

export interface DeviceCreateDto {
  display_name: string
  enabled?: boolean
  location?: string | null
  note?: string | null
}

export interface DeviceUpdateDto {
  display_name?: string
  enabled?: boolean
  location?: string | null
  note?: string | null
}

export interface ProviderApplicationInventoryDto {
  app_id: string
  app_name: string
  version_id: string | null
  updated_at: string | null
  app_type: string | null
  group_id: string | null
}

export interface YingdaoProviderInventoryDto {
  provider: 'yingdao'
  available: boolean
  status:
    | 'not_installed'
    | 'version_unsupported'
    | 'starting'
    | 'need_login'
    | 'interface_unreachable'
    | 'ready'
  status_reason_code: string | null
  status_reason: string | null
  provider_version: string | null
  execution_available?: boolean
  execution_version?: string | null
  execution_unavailable_reason?: string | null
  logged_in: boolean
  account_display: string | null
  account_type: string
  enterprise_account: boolean
  user_id: string | null
  applications: ProviderApplicationInventoryDto[]
  discovered_at: string
}

export interface DeviceProviderInventoryReadDto {
  device_id: string
  provider_code: 'yingdao'
  available: boolean
  provider_version: string | null
  account_display: string | null
  account_type: string | null
  enterprise_account: boolean | null
  last_discovered_at: string
  inventory: YingdaoProviderInventoryDto
  updated_at: string
}

export interface DeviceSkillCapabilityReadDto {
  device_id: string
  skill_id: string
  display_name: string
  runtime: 'python' | 'rpa' | 'discovery'
  provider: string | null
  version: string
  updated_at: string
}

export type WorkerCredentialStatusDto = 'issued' | 'revoked' | 'not_issued'

export interface WorkerCredentialReadDto {
  device_id: string
  status: WorkerCredentialStatusDto
  issued_at: string | null
}

export interface WorkerTokenIssuedReadDto extends WorkerCredentialReadDto {
  token: string
}
