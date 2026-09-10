import { spawnSync } from 'node:child_process'
import { readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const testsDirectory = fileURLToPath(new URL('../dist/tests/', import.meta.url))
const testFiles = readdirSync(testsDirectory, { withFileTypes: true })
  .filter((entry) => entry.isFile() && entry.name.endsWith('.test.js'))
  .map((entry) => path.join(testsDirectory, entry.name))
  .sort()

if (testFiles.length === 0) {
  throw new Error(`没有找到已编译的 Electron 测试：${testsDirectory}`)
}

const result = spawnSync(process.execPath, ['--test', ...testFiles], {
  stdio: 'inherit',
})

if (result.error) {
  throw result.error
}

process.exitCode = result.status ?? 1
