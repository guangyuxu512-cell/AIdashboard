import fs from 'node:fs'
import path from 'node:path'

import {
  FuseV1Options,
  FuseVersion,
  getCurrentFuseWire,
} from '@electron/fuses'

const executableArgument = process.argv[2]
if (!executableArgument) {
  throw new Error('缺少待验证的 Electron EXE 路径')
}

const executablePath = path.resolve(executableArgument)
if (!fs.statSync(executablePath).isFile()) {
  throw new Error(`Electron EXE 不存在：${executablePath}`)
}

const expectedFuses = new Map([
  [FuseV1Options.RunAsNode, false],
  [FuseV1Options.EnableCookieEncryption, true],
  [FuseV1Options.EnableNodeOptionsEnvironmentVariable, false],
  [FuseV1Options.EnableNodeCliInspectArguments, false],
  [FuseV1Options.EnableEmbeddedAsarIntegrityValidation, true],
  [FuseV1Options.OnlyLoadAppFromAsar, true],
  [FuseV1Options.LoadBrowserProcessSpecificV8Snapshot, false],
  [FuseV1Options.GrantFileProtocolExtraPrivileges, false],
  [FuseV1Options.WasmTrapHandlers, true],
])

const actual = await getCurrentFuseWire(executablePath)
if (actual.version !== FuseVersion.V1) {
  throw new Error(`不支持的 Electron Fuse wire 版本：${actual.version}`)
}

const wireEntries = Object.keys(actual).filter((key) => /^\d+$/.test(key))
if (wireEntries.length !== expectedFuses.size) {
  throw new Error(
    `Electron Fuse 数量不匹配：期望 ${expectedFuses.size}，实际 ${wireEntries.length}`,
  )
}

const summary = {}
for (const [fuse, enabled] of expectedFuses) {
  const expectedState = enabled ? '1'.charCodeAt(0) : '0'.charCodeAt(0)
  const actualState = actual[fuse]
  const name = FuseV1Options[fuse]
  if (actualState !== expectedState) {
    throw new Error(
      `${name} 状态不匹配：期望 ${enabled ? 'Enabled' : 'Disabled'}，实际字节 ${actualState}`,
    )
  }
  summary[name] = enabled ? 'Enabled' : 'Disabled'
}

process.stdout.write(
  `${JSON.stringify({ version: actual.version, fuses: summary })}\n`,
)
