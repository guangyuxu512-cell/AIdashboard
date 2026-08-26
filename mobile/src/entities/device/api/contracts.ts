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

export interface DeviceListRequest {
  page: number
  page_size: number
}
