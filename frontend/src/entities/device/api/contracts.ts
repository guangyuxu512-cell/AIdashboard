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

export interface DeviceLocalShopDto {
  local_shop_id: string
  platform_shop_id: string | null
  shop_name: string
  platform: string
  session_status: 'valid' | 'invalid' | 'reauthorization_required' | 'unknown'
  status_observed_at: string | null
  compass_session_status?: 'valid' | 'invalid' | 'reauthorization_required' | 'unknown'
  compass_status_observed_at?: string | null
}

export interface DeviceLocalShopInventoryDto {
  device_id: string
  available: boolean
  last_discovered_at: string | null
  shops: DeviceLocalShopDto[]
}

export interface DeviceShopOverviewDto extends DeviceLocalShopInventoryDto {
  device_name: string
  device_enabled: boolean
  worker_runtime: DeviceRuntimeReadDto | null
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

export interface DeviceSkillCapabilityReadDto {
  device_id: string
  skill_id: string
  display_name: string
  runtime: 'python' | 'rpa' | 'discovery'
  provider: string | null
  version: string
  classification: 'internal' | 'business' | null
  input_schema: Record<string, unknown> | null
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
export type SourcingAccountPresenceDto = {
  accountId: string
  name: string
  sessionStatus: 'unverified' | 'valid' | 'expired' | 'needs_verification'
  sessionCheckedAt: number | null
  workStatus: 'idle' | 'working'
}

export type SourcingAgentPresenceDto = {
  reporterId: string
  installationId: string
  deviceName: string
  appVersion: string
  lastSeenAt: number
  online: boolean
  accounts: SourcingAccountPresenceDto[]
}
