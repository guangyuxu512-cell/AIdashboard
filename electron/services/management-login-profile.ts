import { promises as fs } from 'node:fs'

import {
  isManagementLoginPlatform,
  type ManagementLoginPlatform,
} from '../types'

export interface ManagementLoginProfileMapping {
  platform: ManagementLoginPlatform
  partition: string
  updatedAt: string
}

export type ManagementLoginProfileMappings = Record<
  string,
  ManagementLoginProfileMapping
>

export interface ManagementLoginProfileFileSystem {
  readFile(filePath: string, encoding: 'utf8'): Promise<string>
  writeFile(filePath: string, contents: string, encoding: 'utf8'): Promise<void>
  rename(sourcePath: string, destinationPath: string): Promise<void>
}

export interface ManagementLoginProfileMappingStore {
  load(
    shopId: string,
    platform: ManagementLoginPlatform,
  ): Promise<ManagementLoginProfileMapping | null>
  save(
    shopId: string,
    platform: ManagementLoginPlatform,
    partition: string,
  ): Promise<void>
}

const defaultFileSystem: ManagementLoginProfileFileSystem = {
  readFile: (filePath) => fs.readFile(filePath, 'utf8'),
  writeFile: (filePath, contents) => fs.writeFile(filePath, contents, 'utf8'),
  rename: (sourcePath, destinationPath) =>
    fs.rename(sourcePath, destinationPath),
}

export class ManagementLoginProfileStore implements ManagementLoginProfileMappingStore {
  private operationQueue: Promise<void> = Promise.resolve()

  constructor(
    private readonly resolveFilePath: () => string,
    private readonly fileSystem: ManagementLoginProfileFileSystem = defaultFileSystem,
    private readonly now: () => Date = () => new Date(),
  ) {}

  async load(
    shopId: string,
    platform: ManagementLoginPlatform,
  ): Promise<ManagementLoginProfileMapping | null> {
    return this.runExclusively(async () => {
      const mappings = await this.readMappings(this.resolveFilePath())
      return parseManagementLoginProfile(mappings[shopId], platform)
    })
  }

  async save(
    shopId: string,
    platform: ManagementLoginPlatform,
    partition: string,
  ): Promise<void> {
    return this.runExclusively(async () => {
      const filePath = this.resolveFilePath()
      const mappings = await this.readMappings(filePath)
      mappings[shopId] = {
        platform,
        partition,
        updatedAt: this.now().toISOString(),
      }

      const temporaryPath = `${filePath}.tmp`
      const contents = JSON.stringify(mappings, null, 2)
      try {
        await this.fileSystem.writeFile(temporaryPath, contents, 'utf8')
      } catch (error) {
        throw new Error(
          `无法写入本地登录环境映射（${describeFileError(error)}），原文件未被覆盖`,
        )
      }
      try {
        await this.fileSystem.rename(temporaryPath, filePath)
      } catch (error) {
        throw new Error(
          `无法替换本地登录环境映射（${describeFileError(error)}），原文件未被覆盖`,
        )
      }
    })
  }

  private async readMappings(
    filePath: string,
  ): Promise<ManagementLoginProfileMappings> {
    let contents: string
    try {
      contents = await this.fileSystem.readFile(filePath, 'utf8')
    } catch (error) {
      if (hasFileSystemCode(error, 'ENOENT')) return createEmptyMappings()
      throw new Error(
        `无法读取本地登录环境映射（${describeFileError(error)}），原文件未被修改`,
      )
    }

    let value: unknown
    try {
      value = JSON.parse(contents)
    } catch {
      throw new Error('本地登录环境映射文件损坏，已保留原文件')
    }
    const mappings = parseManagementLoginProfileMappings(value)
    if (!mappings) {
      throw new Error('本地登录环境映射文件结构无效，已保留原文件')
    }
    return mappings
  }

  private async runExclusively<T>(operation: () => Promise<T>): Promise<T> {
    const previous = this.operationQueue
    let release: () => void = () => undefined
    this.operationQueue = new Promise<void>((resolve) => {
      release = resolve
    })
    await previous
    try {
      return await operation()
    } finally {
      // 同一 Electron Main 可同时完成多店接入，读改写必须串行以保留所有映射。
      release()
    }
  }
}

export function parseManagementLoginProfile(
  value: unknown,
  platform: ManagementLoginPlatform,
): ManagementLoginProfileMapping | null {
  const mapping = parseStoredManagementLoginProfile(value)
  return mapping?.platform === platform ? mapping : null
}

export function parseManagementLoginProfileMappings(
  value: unknown,
): ManagementLoginProfileMappings | null {
  if (!isRecord(value)) return null
  const mappings = createEmptyMappings()
  for (const [shopId, mappingValue] of Object.entries(value)) {
    const mapping = parseStoredManagementLoginProfile(mappingValue)
    if (!mapping) return null
    mappings[shopId] = mapping
  }
  return mappings
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

function parseStoredManagementLoginProfile(
  value: unknown,
): ManagementLoginProfileMapping | null {
  if (!isRecord(value)) return null
  if (
    !isManagementLoginPlatform(value.platform) ||
    typeof value.partition !== 'string' ||
    !/^persist:management-login-[0-9a-f-]{36}$/i.test(value.partition) ||
    typeof value.updatedAt !== 'string'
  ) {
    return null
  }
  return {
    platform: value.platform,
    partition: value.partition,
    updatedAt: value.updatedAt,
  }
}

function createEmptyMappings(): ManagementLoginProfileMappings {
  return Object.create(null) as ManagementLoginProfileMappings
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function hasFileSystemCode(error: unknown, code: string): boolean {
  if (typeof error !== 'object' || error === null || !('code' in error)) {
    return false
  }
  return (error as { code?: unknown }).code === code
}

function describeFileError(error: unknown): string {
  if (hasFileSystemCode(error, 'EACCES') || hasFileSystemCode(error, 'EPERM')) {
    return '没有文件访问权限'
  }
  if (error instanceof Error && error.message) return error.message
  return '文件系统错误'
}
