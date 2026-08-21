import type { ManagementLoginPlatform } from '../types'

export interface ManagementLoginProfileMapping {
  platform: ManagementLoginPlatform
  partition: string
  updatedAt: string
}

export function parseManagementLoginProfile(
  value: unknown,
  platform: ManagementLoginPlatform,
): ManagementLoginProfileMapping | null {
  if (!value || typeof value !== 'object') return null
  const mapping = value as Record<string, unknown>
  if (
    mapping.platform !== platform ||
    typeof mapping.partition !== 'string' ||
    !/^persist:management-login-[0-9a-f-]{36}$/i.test(mapping.partition) ||
    typeof mapping.updatedAt !== 'string'
  ) {
    return null
  }
  return {
    platform,
    partition: mapping.partition,
    updatedAt: mapping.updatedAt,
  }
}

export function resolveManagementLoginPartition(
  attemptId: string,
  mapping: ManagementLoginProfileMapping | null,
): { partition: string; profileReused: boolean } {
  return mapping
    ? { partition: mapping.partition, profileReused: true }
    : {
        partition: `persist:management-login-${attemptId}`,
        profileReused: false,
      }
}
