import dayjs from 'dayjs'

import type { ShopPlatform } from '@/entities/shop'
import { apiMode, type ApiMode } from '@/shared/api'

import type {
  CredentialCreateInput,
  CredentialStatusViewModel,
  CredentialUpdateInput,
} from '../model/types'
import type { CredentialStatusReadDto } from './contracts'
import { credentialApi } from './credential-api'

export interface CredentialDataSource {
  readonly mode: ApiMode
  getForShop(
    shopId: string,
    platform: ShopPlatform,
  ): Promise<CredentialStatusViewModel>
  create(input: CredentialCreateInput): Promise<CredentialStatusViewModel>
  update(input: CredentialUpdateInput): Promise<CredentialStatusViewModel>
}

function mapCredentialStatus(
  dto: CredentialStatusReadDto,
): CredentialStatusViewModel {
  return {
    credentialId: dto.credential_id,
    platform: dto.platform,
    maskedIdentifier: dto.masked_identifier,
    configured: dto.configured,
    passwordConfigured: dto.configured,
    enabled: dto.enabled,
    preferredVerificationChannel: dto.preferred_verification_channel,
    updatedAtDisplay: dto.updated_at
      ? dayjs(dto.updated_at).format('YYYY-MM-DD HH:mm')
      : null,
  }
}

export function createMockCredentialDataSource(): CredentialDataSource {
  const statuses = new Map<string, CredentialStatusViewModel>()
  let sequence = 1

  return {
    mode: 'mock',
    async getForShop(shopId, platform) {
      return (
        statuses.get(shopId) ?? {
          credentialId: null,
          platform,
          maskedIdentifier: null,
          configured: false,
          passwordConfigured: false,
          enabled: false,
          preferredVerificationChannel: null,
          updatedAtDisplay: null,
        }
      )
    },
    async create(input) {
      const status: CredentialStatusViewModel = {
        credentialId: `credential-fixture-${sequence++}`,
        platform: input.platform,
        maskedIdentifier: maskFixtureIdentifier(input.loginIdentifier),
        configured: true,
        passwordConfigured: true,
        enabled: true,
        preferredVerificationChannel: input.preferredVerificationChannel,
        updatedAtDisplay: dayjs().format('YYYY-MM-DD HH:mm'),
      }
      statuses.set(input.shopId, status)
      return status
    },
    async update(input) {
      const entry = [...statuses.entries()].find(
        ([, status]) => status.credentialId === input.credentialId,
      )
      if (!entry) throw new Error('账号凭证不存在')
      const [shopId, existing] = entry
      const updated: CredentialStatusViewModel = {
        ...existing,
        maskedIdentifier: input.loginIdentifier
          ? maskFixtureIdentifier(input.loginIdentifier)
          : existing.maskedIdentifier,
        preferredVerificationChannel:
          input.preferredVerificationChannel ??
          existing.preferredVerificationChannel,
        updatedAtDisplay: dayjs().format('YYYY-MM-DD HH:mm'),
      }
      statuses.set(shopId, updated)
      return updated
    },
  }
}

function maskFixtureIdentifier(value: string): string {
  if (value.includes('@')) {
    const [local = '', domain = ''] = value.split('@')
    return `${local.slice(0, 3)}***@${domain}`
  }
  if (/^\d{7,}$/.test(value))
    return `${value.slice(0, 3)}****${value.slice(-4)}`
  return `${value.slice(0, 2)}***${value.slice(-2)}`
}

const realCredentialDataSource: CredentialDataSource = {
  mode: 'real',
  async getForShop(shopId) {
    return mapCredentialStatus(await credentialApi.getForShop(shopId))
  },
  async create(input) {
    return mapCredentialStatus(
      await credentialApi.create({
        shop_id: input.shopId,
        login_identifier: input.loginIdentifier,
        secret: input.password,
        preferred_verification_channel: input.preferredVerificationChannel,
      }),
    )
  },
  async update(input) {
    return mapCredentialStatus(
      await credentialApi.update(input.credentialId, {
        ...(input.loginIdentifier
          ? { login_identifier: input.loginIdentifier }
          : {}),
        ...(input.password ? { secret: input.password } : {}),
        ...(input.preferredVerificationChannel
          ? {
              preferred_verification_channel:
                input.preferredVerificationChannel,
            }
          : {}),
      }),
    )
  },
}

export function createCredentialDataSource(
  mode: ApiMode,
): CredentialDataSource {
  return mode === 'real'
    ? realCredentialDataSource
    : createMockCredentialDataSource()
}

export const credentialDataSource = createCredentialDataSource(apiMode)
