import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const productionUiFiles = [
  '../../src/pages/HomePage.vue',
  '../../src/pages/ComingSoonPage.vue',
  '../../src/pages/devices/DeviceCenterPage.vue',
  '../../src/pages/devices/DeviceDetailPage.vue',
  '../../src/pages/tasks/TaskCenterPage.vue',
  '../../src/pages/tasks/TaskDetailPage.vue',
  '../../src/features/device-center/ui/DeviceOverviewCards.vue',
  '../../src/features/device-center/ui/DeviceInfiniteList.vue',
  '../../src/features/device-center/ui/ActiveTaskSummary.vue',
  '../../src/features/device-center/ui/DeviceYingdaoSummary.vue',
  '../../src/features/device-center/ui/DeviceCapabilityPanel.vue',
  '../../src/features/task-center/ui/TaskInfiniteList.vue',
  '../../src/features/task-center/ui/TaskFilterSheet.vue',
  '../../src/features/task-runtime/ui/TaskRuntimeLog.vue',
]

function templateOf(relativePath: string): string {
  const source = readFileSync(
    fileURLToPath(new URL(relativePath, import.meta.url)),
    'utf8',
  )
  return source.match(/<template>([\s\S]*?)<\/template>/)?.[1] ?? ''
}

describe('formal Mobile UI copy', () => {
  it('does not expose implementation or data-scope explanations', () => {
    const templates = productionUiFiles.map(templateOf).join('\n')
    const forbidden = [
      '当前仅统计',
      '当前已加载',
      '每 15 秒刷新',
      '每15秒刷新',
      '当前展示',
      '已保留上次',
      'Backend',
      'API',
      'Contract',
      'worker_runtime',
      'status=running',
    ]

    for (const copy of forbidden) expect(templates).not.toContain(copy)
  })

  it('keeps the construction placeholder to one product sentence', () => {
    const template = templateOf('../../src/pages/ComingSoonPage.vue')

    expect(template).toContain('功能建设中')
    expect(template).not.toMatch(/Auth|RBAC|架构|未来|开放/)
  })
})
