import { expect, test, type Page } from '@playwright/test'

// Formal API interception only: no platform calls, fake Real strategies or
// Electron claims. The integrator verifies the same code in its unique window.
const themes = [
  ['graphite', '石墨浅色'],
  ['forest', '森林绿'],
  ['coral', '珊瑚红'],
  ['midnight', '午夜青'],
] as const
async function settle(page: Page) {
  await expect
    .poll(() =>
      page
        .locator('body')
        .evaluate(
          (element) =>
            element
              .getAnimations({ subtree: true })
              .filter(
                (animation) =>
                  animation.playState === 'running' &&
                  animation.effect?.getTiming().iterations !== Infinity,
              ).length,
        ),
    )
    .toBe(0)
}

test('Real preserves strategy management, and four-level categories stay visible, scrollable and parent-all selectable', async ({
  page,
}, info) => {
  test.setTimeout(180000)
  const unexpected: string[] = [],
    mockModules: string[] = [],
    posts: string[] = []
  page.on('request', (request) => {
    if (request.url().includes('selection-mock-handlers'))
      mockModules.push(request.url())
    if (request.method() === 'POST') posts.push(new URL(request.url()).pathname)
  })
  await page.route(/^https?:\/\/[^/]+\/api\//, async (route) => {
    const path = new URL(route.request().url()).pathname
    let data: unknown
    if (path === '/api/v1/auth/me')
      data = { user_id: 'restoration-person', display_name: '隔离前端契约验证' }
    else if (path === '/api/v1/access/me/teams')
      data = [
        {
          membership_id: 'restoration-member',
          team_id: 'restoration-team',
          team_name: '契约验证团队',
          team_enabled: true,
          membership_enabled: true,
          role_code: 'member',
          data_scope: 'team',
        },
      ]
    else if (path === '/api/v1/access-management/me/module-access')
      data = {
        module_codes: ['product-selection'],
        is_super_account: false,
        is_access_administrator: false,
      }
    else if (path === '/api/v1/shops')
      data = {
        items: [
          {
            shop_id: 'restoration-shop',
            display_name: '授权店铺',
            platform: 'douyin',
            enabled: true,
            owner_user_id: null,
            note: null,
            created_at: '2026-10-01T00:00:00Z',
            updated_at: '2026-10-01T00:00:00Z',
            deleted_at: null,
            session_status: 'valid',
          },
        ],
        total: 1,
        page: 1,
        page_size: 100,
      }
    else if (path === '/api/v1/product-selection/capabilities')
      data = {
        execution_enabled: true,
        manual_execution_available: true,
        unavailable_reason: null,
      }
    else if (path === '/api/v1/product-selection/runs')
      data = { items: [], total: 0, page: 1, page_size: 1 }
    else if (path === '/api/v1/product-selection/categories')
      data = {
        shop_id: 'restoration-shop',
        industry_id: '7',
        nodes: [
          {
            category_id: '7',
            name: '真实行业',
            children: [
              {
                category_id: '1001',
                name: '二级父类目',
                children: [
                  {
                    category_id: '1002',
                    name: '三级父类目',
                    children: Array.from({ length: 50 }, (_, index) => ({
                      category_id: `200${index}`,
                      name: `四级类目${index}`,
                      children: [],
                    })),
                  },
                ],
              },
            ],
          },
        ],
      }
    else {
      unexpected.push(path)
      await route.abort()
      return
    }
    await route.fulfill({ json: data })
  })
  await page.goto('/#/product-selection?tab=selection-strategy')
  const drawer = page.locator('.n-drawer')
  const field = (label: string) =>
    drawer
      .locator('.n-form-item')
      .filter({
        has: page.locator('.n-form-item-label', {
          hasText: new RegExp(`^${label}$`),
        }),
      })
      .last()
  for (const viewport of [
    { width: 960, height: 640 },
    { width: 1280, height: 800 },
    { width: 1366, height: 768 },
    { width: 1440, height: 900 },
  ]) {
    await page.setViewportSize(viewport)
    for (const [id, label] of themes) {
      await page.getByRole('button', { name: '切换主题' }).click()
      await page
        .locator('.n-dropdown')
        .getByText(label, { exact: true })
        .click()
      await expect(
        page.getByRole('textbox', { name: '搜索策略名称' }),
      ).toBeVisible()
      await expect(
        page.getByRole('button', { name: '达人登录', exact: true }),
      ).toBeVisible()
      await expect(
        page.getByText('策略保存与定时执行待接入', { exact: true }),
      ).toBeVisible()
      await settle(page)
      await page.screenshot({
        path: info.outputPath(
          `${id}-${viewport.width}-restored-strategy-list.png`,
        ),
        animations: 'disabled',
      })
      await page.getByRole('button', { name: '新建策略', exact: true }).click()
      await expect(field('请求店铺')).toBeVisible()
      await expect(field('达人账号')).toBeVisible()
      await expect(
        drawer.getByRole('textbox', { name: '策略名称' }),
      ).toBeVisible()
      await expect(field('达人账号').locator('.n-base-selection')).toHaveClass(
        /disabled/,
      )
      await field('请求店铺').locator('.n-base-selection').click()
      await page.getByText('授权店铺', { exact: true }).last().click()
      await field('类目').locator('.n-base-selection').click()
      await page.getByText('真实行业', { exact: true }).last().click()
      await page.getByText('二级父类目', { exact: true }).last().click()
      await page.getByText('三级父类目', { exact: true }).last().click()
      const menu = page.locator('.n-cascader-menu')
      await expect(menu.locator('.n-cascader-submenu')).toHaveCount(4)
      await settle(page)
      const bounds = (await menu.boundingBox())!
      expect(bounds.x).toBeGreaterThanOrEqual(0)
      expect(bounds.y).toBeGreaterThanOrEqual(0)
      expect(bounds.x + bounds.width).toBeLessThanOrEqual(viewport.width)
      expect(bounds.y + bounds.height).toBeLessThanOrEqual(viewport.height)
      await page.screenshot({
        path: info.outputPath(`${id}-${viewport.width}-four-level-menu.png`),
        animations: 'disabled',
      })
      const lastColumn = menu.locator('.n-cascader-submenu').last()
      await lastColumn.locator('.v-vl').evaluate((element) => {
        element.scrollTop = element.scrollHeight
      })
      await expect(
        lastColumn.getByText('四级类目49', { exact: true }),
      ).toBeVisible()
      await lastColumn.getByText('四级类目49', { exact: true }).click()
      await expect(field('类目').locator('.n-cascader')).toContainText(
        '四级类目49',
      )
      await field('类目').locator('.n-base-selection').click()
      await menu
        .locator('.n-cascader-submenu')
        .last()
        .locator('.v-vl')
        .evaluate((element) => {
          element.scrollTop = 0
        })
      await menu
        .locator('.n-cascader-submenu')
        .last()
        .getByText('全部', { exact: true })
        .click()
      await expect(field('类目').locator('.n-cascader')).toContainText(
        '三级父类目 / 全部',
      )
      await field('定时执行').getByRole('switch').click()
      await field('执行频率').locator('.n-base-selection').click()
      await page
        .locator('.n-base-select-menu')
        .getByText('每日', { exact: true })
        .click()
      await expect(field('每日时间').getByRole('textbox')).toHaveValue('09:00')
      await expect(field('策略状态').getByRole('switch')).toBeDisabled()
      await expect(
        drawer.getByRole('button', { name: '保存策略', exact: true }),
      ).toBeDisabled()
      await drawer
        .locator('.n-drawer-body-content-wrapper')
        .evaluate((element) => {
          element.scrollTop = element.scrollHeight
        })
      await page.mouse.move(20, 20)
      await expect(
        page.locator('.n-tooltip:visible, .n-popover:visible'),
      ).toHaveCount(0)
      await settle(page)
      await page.screenshot({
        path: info.outputPath(`${id}-${viewport.width}-restored-schedule.png`),
        animations: 'disabled',
      })
      await drawer.getByRole('button', { name: '取消', exact: true }).click()
    }
  }
  expect(unexpected).toEqual([])
  expect(mockModules).toEqual([])
  expect(posts).toEqual([])
})
