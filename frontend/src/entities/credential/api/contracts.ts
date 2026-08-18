import type { BackendShopPlatform } from '@/entities/shop'

export type VerificationChannelDto = 'manual' | 'email' | 'sms_hardware'

export interface CredentialCreateDto {
  shop_id: string
  login_identifier: string
  secret: string
  preferred_verification_channel: VerificationChannelDto
}

export interface CredentialUpdateDto {
  login_identifier?: string
  secret?: string
  preferred_verification_channel?: VerificationChannelDto
}

export interface CredentialStatusReadDto {
  credential_id: string | null
  platform: BackendShopPlatform
  masked_identifier: string | null
  configured: boolean
  enabled: boolean
  preferred_verification_channel: VerificationChannelDto | null
  updated_at: string | null
}
