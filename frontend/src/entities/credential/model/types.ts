import type { ShopPlatform } from '@/entities/shop'

export type VerificationChannel = 'manual' | 'email' | 'sms_hardware'

export interface CredentialStatusViewModel {
  credentialId: string | null
  platform: ShopPlatform
  maskedIdentifier: string | null
  configured: boolean
  passwordConfigured: boolean
  enabled: boolean
  preferredVerificationChannel: VerificationChannel | null
  updatedAtDisplay: string | null
}

export interface CredentialCreateInput {
  shopId: string
  platform: ShopPlatform
  loginIdentifier: string
  password: string
  preferredVerificationChannel: VerificationChannel
}

export interface CredentialUpdateInput {
  credentialId: string
  loginIdentifier?: string
  password?: string
  preferredVerificationChannel?: VerificationChannel
}
