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
  package_version: string
  entrypoint: string
}

export interface YingdaoProviderInventoryDto {
  provider: 'yingdao'
  available: boolean
  provider_version: string
  logged_in: boolean
  account_display: string
  account_type: string
  enterprise_account: boolean
  user_id: string
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
