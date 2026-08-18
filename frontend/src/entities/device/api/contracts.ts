export interface DeviceReadDto {
  device_id: string
  display_name: string
  enabled: boolean
  location: string | null
  note: string | null
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
