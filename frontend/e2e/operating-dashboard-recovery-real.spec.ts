import { expect, test } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import type {
  mapOperatingDashboardRead,
  OperatingDashboardCollectionJobDto,
} from '../src/features/operating-dashboard/api/operating-dashboard-api'

// Real Renderer, every API intercepted. Responses originate in the dedicated
// Feature PostgreSQL/ASGI tests, whose platform adapters are synthetic.
// No production, native Electron or real platform evidence is claimed here.
type Snapshot = {
  before: Parameters<typeof mapOperatingDashboardRead>[0]
  after: Parameters<typeof mapOperatingDashboardRead>[0]
  accepted: OperatingDashboardCollectionJobDto
  finished: OperatingDashboardCollectionJobDto
  steps: {
    original_job_id: string
    original_item_id: string
    request: Record<string, unknown>
    accepted: OperatingDashboardCollectionJobDto
    finished: OperatingDashboardCollectionJobDto
    after: Parameters<typeof mapOperatingDashboardRead>[0]
  }[]
}
const proofPath = process.env.PLAYWRIGHT_OPERATING_RECOVERY_PROOF
test.skip(
  process.env.PLAYWRIGHT_API_MODE !== 'real' || !proofPath,
  'Requires the isolated Real renderer and the dedicated Feature API proof',
)

for (const preset of ['graphite', 'forest', 'coral', 'midnight']) {
  test(`${preset}: explicit recovery consumes the same Feature API receipts and keeps complete updates read-only`, async ({
    page,
  }, info) => {
    test.setTimeout(60_000)
    const proof = JSON.parse(await readFile(proofPath!, 'utf8')) as Snapshot
    expect(proof.steps).toHaveLength(8)
    await page.setViewportSize({
      width: preset === 'midnight' ? 1024 : 1440,
      height: 900,
    })
    await page.addInitScript(
      (theme) => localStorage.setItem('control-center.theme-mode', theme),
      preset,
    )
    const unexpected: string[] = []
    const pageErrors: string[] = []
    let recoveryPosts = 0,
      ordinaryPosts = 0,
      completedSteps = 0
    let currentRead = proof.before
    const releaseProgress: (() => void)[] = []
    const progress = proof.steps.map(
      (_, index) =>
        new Promise<void>((resolve) => {
          releaseProgress[index] = resolve
        }),
    )
    let lastRange: string | null = null
    page.on('pageerror', (error) => pageErrors.push(error.message))
    await page.route('**/*', async (route) => {
      const request = route.request(),
        url = new URL(request.url()),
        path = url.pathname
      if (url.hostname !== '127.0.0.1') {
        unexpected.push(`external:${url.hostname}`)
        return route.abort()
      }
      if (!path.startsWith('/api/')) return route.continue()
      let data: unknown
      let status = 200
      if (path === '/api/v1/auth/me')
        data = { user_id: 'recovery-user', display_name: '隔离恢复验证' }
      else if (path === '/api/v1/access/me/teams')
        data = [
          {
            membership_id: 'recovery-member',
            team_id: 'recovery-team',
            team_name: '隔离恢复团队',
            team_enabled: true,
            membership_enabled: true,
            role_code: 'member',
            data_scope: 'team',
          },
        ]
      else if (path === '/api/v1/access-management/me/module-access')
        data = {
          module_codes: ['shop'],
          is_super_account: false,
          is_access_administrator: false,
        }
      else if (
        path === '/api/v1/operating-dashboard' &&
        request.method() === 'GET'
      ) {
        lastRange = `${url.searchParams.get('start_date')}/${url.searchParams.get('end_date')}`
        data = currentRead
      } else if (path.endsWith('/retry') && request.method() === 'POST') {
        const step = proof.steps[completedSteps]
        expect(path).toBe(
          `/api/v1/operating-dashboard/collections/${step.original_job_id}/retry`,
        )
        recoveryPosts++
        expect(lastRange).toBe('2026-10-10/2026-10-15')
        expect(request.postDataJSON()).toEqual(step.request)
        data = step.accepted
        status = 202
      } else if (
        path.startsWith('/api/v1/operating-dashboard/collections/') &&
        request.method() === 'GET'
      ) {
        const index = proof.steps.findIndex((step) =>
          path.endsWith(`/${step.accepted.collection_job_id}`),
        )
        expect(index).toBeGreaterThanOrEqual(0)
        await progress[index]
        if (index === completedSteps) {
          currentRead = proof.steps[index].after
          completedSteps++
        }
        data = proof.steps[index].finished
      } else if (
        path === '/api/v1/operating-dashboard/collections' &&
        request.method() === 'POST' &&
        completedSteps === 8
      ) {
        ordinaryPosts++
        expect(request.postDataJSON()).toMatchObject({
          start_date: '2026-10-10',
          end_date: '2026-10-15',
        })
        data = {
          state: 'up_to_date',
          message: '所选范围数据已齐全，无需补采。',
          collection_job: null,
          missing_shop_days: 0,
          queued_shop_days: 0,
          active_shop_days: 0,
          blocked_shop_days: 0,
          waiting_shop_days: 0,
          refund_attention_shop_days: 0,
          not_operating_shop_days: 0,
        }
      } else {
        unexpected.push(`${request.method()}:${path}`)
        return route.abort()
      }
      return route.fulfill({
        status,
        contentType: 'application/json',
        body: JSON.stringify(data),
      })
    })
    await page.goto('/#/operating-dashboard')
    await expect(page.getByRole('region', { name: '经营概览' })).toBeVisible()
    await page.getByText('自定义', { exact: true }).click()
    await page.getByPlaceholder('开始日期').fill('2026-10-10')
    await page.getByPlaceholder('开始日期').press('Enter')
    await page.getByPlaceholder('结束日期').fill('2026-10-15')
    await page.getByPlaceholder('结束日期').press('Enter')
    await page.getByRole('heading', { name: /成交趋势/ }).click()
    await expect.poll(() => lastRange).toBe('2026-10-10/2026-10-15')
    expect(recoveryPosts).toBe(0)
    for (const [index, step] of proof.steps.entries()) {
      const source = index === 0 ? proof.before : proof.steps[index - 1].after
      const sample = source.coverage.missing_samples.find(
        (row) =>
          row.session_recovery?.collection_item_id === step.original_item_id,
      )!
      expect(sample).toBeDefined()
      await page.getByRole('heading', { name: /成交趋势/ }).click()
      await page.getByRole('button', { name: '查看缺失' }).click()
      const action = page
        .locator('.operating-dashboard-filter__missing-item')
        .filter({ hasText: sample.shop_name })
        .filter({ hasText: sample.business_date })
        .getByRole('button', { name: /恢复/ })
      await expect(action).toBeVisible()
      await expect(action).toBeEnabled()
      await action.scrollIntoViewIfNeeded()
      if (index === 0)
        await page.screenshot({
          path: info.outputPath(`${preset}-recovery-eligibility.png`),
          fullPage: true,
        })
      await action.click()
      await expect(
        page.locator('.operating-dashboard-filter__feedback'),
      ).toContainText('已提交恢复')
      await expect(action).toBeDisabled()
      expect(recoveryPosts).toBe(index + 1)
      releaseProgress[index]()
      await expect(
        page.locator('.operating-dashboard-filter__feedback'),
      ).toContainText('已完成 1 条')
      await expect(
        page.locator('.operating-dashboard-filter__coverage'),
      ).toContainText(`${step.after.coverage.collected_shop_days}/12`)
    }
    await page.getByRole('button', { name: '更新数据', exact: true }).click()
    await expect(
      page.locator('.operating-dashboard-filter__feedback'),
    ).toContainText('无需补采')
    await page.getByRole('button', { name: '更新数据', exact: true }).click()
    await expect.poll(() => ordinaryPosts).toBe(2)
    expect(recoveryPosts).toBe(8)
    await page.screenshot({
      path: info.outputPath(`${preset}-recovery-complete.png`),
      fullPage: true,
    })
    expect(pageErrors).toEqual([])
    expect(unexpected).toEqual([])
  })
}
