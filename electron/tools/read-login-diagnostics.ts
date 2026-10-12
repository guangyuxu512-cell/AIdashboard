import { readFile, stat } from 'node:fs/promises'
import path from 'node:path'
import { resolveDesktopUserDataPath } from '../config/runtime'
import { safeLoginDiagnostic } from '../services/login-diagnostics'
import { isUuid } from '../types'

async function main() {
  const args = process.argv.slice(2)
  const requested =
    args.length === 2 && args[0] === '--correlation' ? args[1] : undefined
  if ((args.length && !requested) || (requested && !isUuid(requested)))
    throw new Error('仅支持 --correlation UUID；不接受路径或任意查询')
  if (!process.env.APPDATA) throw new Error('无法确定当前Windows用户日志目录')
  const filePath = path.join(
    resolveDesktopUserDataPath(process.env.APPDATA),
    'diagnostics',
    'shop-login.jsonl',
  )
  const records = []
  for (const file of [filePath + '.1', filePath]) {
    const size = await stat(file)
      .then((item) => item.size)
      .catch(() => 0)
    if (!size || size > 512 * 1024) continue
    const content = await readFile(file, 'utf8').catch(() => '')
    for (const line of content.split('\n')) {
      if (line.length > 2048) continue
      try {
        const safe = safeLoginDiagnostic(JSON.parse(line), true)
        if (safe && (!requested || safe.correlationId === requested))
          records.push(safe)
      } catch {
        /* Drop malformed or untrusted local lines without printing them. */
      }
    }
  }
  for (const record of records.slice(-200)) console.log(JSON.stringify(record))
  if (!records.length)
    console.info('未找到白名单点击记录；没有记录不等于已经定位根因。')
}
void main().catch(() => {
  console.error('无法读取白名单登录诊断；请核对匹配桌面版本及日志文件权限。')
  process.exitCode = 1
})
