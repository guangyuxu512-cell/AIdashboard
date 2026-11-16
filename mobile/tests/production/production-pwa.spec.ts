import { expect, test, type Page, type Route } from '@playwright/test'

import {
  createMobileAuthApiFixture,
  type MobileAuthApiFixture,
  type MobileAuthApiFixtureOptions,
} from '../e2e/auth-api-fixture'

async function fulfillJson(route: Route, body: unknown): Promise<void> {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

async function installProductionApi(
  page: Page,
  options: MobileAuthApiFixtureOptions = {},
): Promise<MobileAuthApiFixture> {
  const auth = createMobileAuthApiFixture(options)
  await page.route('**/api/v1/**', async (route) => {
    if (await auth.handle(route)) return

    const request = route.request()
    const pathname = new URL(request.url()).pathname
    if (request.method() === 'GET' && pathname === '/api/v1/devices') {
      await fulfillJson(route, { items: [], total: 0, page: 1, page_size: 20 })
      return
    }
    if (request.method() === 'GET' && pathname === '/api/v1/tasks') {
      await fulfillJson(route, { items: [], total: 0, page: 1, page_size: 20 })
      return
    }
    await route.fulfill({ status: 404 })
  })
  return auth
}

async function expectNoHorizontalOverflow(page: Page): Promise<void> {
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true)
}

async function expectThemeChrome(
  page: Page,
  theme: 'light' | 'dark',
): Promise<void> {
  const expectedThemeColor = theme === 'dark' ? '#07111d' : '#fbfcfe'
  const expectedAppleStatus = theme === 'dark' ? 'black-translucent' : 'default'

  await expect(
    page.locator('meta[name="theme-color"][data-mobile-theme-color]'),
  ).toHaveAttribute('content', expectedThemeColor)
  await expect(
    page.locator('meta[name="apple-mobile-web-app-status-bar-style"]'),
  ).toHaveAttribute('content', expectedAppleStatus)

  const backgrounds = await page.evaluate(() => {
    const probe = document.createElement('span')
    probe.style.background = 'var(--mobile-root-background)'
    document.body.append(probe)
    const expected = getComputedStyle(probe).backgroundImage
    probe.remove()

    return {
      app: getComputedStyle(document.querySelector<HTMLElement>('#app')!)
        .backgroundImage,
      expected,
    }
  })
  expect(backgrounds.app).toBe(backgrounds.expected)
}

test('production output exposes the Mobile document, manifest and hashed assets below /mobile/', async ({
  request,
}) => {
  const documentResponse = await request.get('/mobile/')
  expect(documentResponse.status()).toBe(200)
  const document = await documentResponse.text()
  expect(document).toContain('href="/mobile/manifest.webmanifest"')
  expect(document).not.toContain('/src/main.ts')

  const assetPaths = Array.from(
    document.matchAll(/(?:src|href)="(\/mobile\/assets\/[^"]+)"/g),
    (match) => match[1],
  )
  expect(assetPaths.length).toBeGreaterThanOrEqual(2)
  for (const assetPath of assetPaths) {
    expect((await request.get(assetPath)).status()).toBe(200)
  }

  const manifestResponse = await request.get('/mobile/manifest.webmanifest')
  expect(manifestResponse.status()).toBe(200)
  await expect(manifestResponse.json()).resolves.toMatchObject({
    id: '/mobile/',
    start_url: '/mobile/',
    scope: '/mobile/',
    display: 'standalone',
  })
  expect((await request.get('/mobile/icons/icon-192.png')).status()).toBe(200)
  expect((await request.get('/mobile/icons/icon-512.png')).status()).toBe(200)
  expect(
    (await request.get('/mobile/icons/apple-touch-icon.png')).status(),
  ).toBe(200)
})

test('Chromium accepts the scoped install manifest without a service worker', async ({
  page,
  context,
}) => {
  await installProductionApi(page)
  await page.goto('/mobile/#/devices')

  const devtools = await context.newCDPSession(page)
  const appManifest = await devtools.send('Page.getAppManifest')
  const installability = await devtools.send('Page.getInstallabilityErrors')

  expect(appManifest.url).toBe(
    'http://127.0.0.1:4176/mobile/manifest.webmanifest',
  )
  expect(appManifest.errors).toEqual([])
  expect(installability.installabilityErrors).toEqual([])
})

test('login deep link, Session restore and logout remain inside the production base', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await installProductionApi(page, { authenticated: false })

  await page.goto('/mobile/#/login')
  await page.getByPlaceholder('请输入登录账号').fill('operator')
  await page.getByPlaceholder('请输入密码').fill('correct-password')
  await page.getByRole('button', { name: '登录', exact: true }).click()

  await expect(page).toHaveURL(/\/mobile\/#\/devices$/)
  await page.reload()
  await expect(page).toHaveURL(/\/mobile\/#\/devices$/)
  await page.getByRole('tab', { name: '我的' }).click()
  await expect(page).toHaveURL(/\/mobile\/#\/me$/)
  await page.getByRole('button', { name: '退出登录' }).click()
  await expect(page).toHaveURL(/\/mobile\/#\/login$/)
})

test('production base preserves Team selection, X-Team-ID and module route access', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const auth = await installProductionApi(page, {
    authenticated: false,
    moduleCodes: ['task'],
    teams: [
      {
        membershipId: 'membership-a',
        teamId: 'team-a',
        teamName: '团队 A',
        teamEnabled: true,
        membershipEnabled: true,
      },
      {
        membershipId: 'membership-b',
        teamId: 'team-b',
        teamName: '团队 B',
        teamEnabled: true,
        membershipEnabled: true,
      },
    ],
  })

  await page.goto('/mobile/#/login')
  await page.getByPlaceholder('请输入登录账号').fill('operator')
  await page.getByPlaceholder('请输入密码').fill('correct-password')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.getByText('团队 B', { exact: true }).click()
  await page.getByRole('button', { name: '进入中控台' }).click()

  await expect(page).toHaveURL(/\/mobile\/#\/tasks$/)
  expect(auth.teamHeaders).toContain('team-b')
  await expect(
    page.getByTestId('mobile-bottom-navigation-devices'),
  ).toHaveCount(0)
  await page.goto('/mobile/#/devices')
  await expect(page).toHaveURL(/\/mobile\/#\/permission-denied$/)
})

for (const width of [360, 375, 390, 430]) {
  for (const theme of ['light', 'dark'] as const) {
    test(`production Mobile ${width}px ${theme} keeps Device and Task layouts stable`, async ({
      page,
    }) => {
      const consoleErrors: string[] = []
      page.on('console', (message) => {
        if (message.type() === 'error') consoleErrors.push(message.text())
      })
      page.on('pageerror', (error) => consoleErrors.push(error.message))
      await page.setViewportSize({ width, height: width === 360 ? 640 : 844 })
      await page.addInitScript((mode) => {
        window.localStorage.setItem('control-center.mobile.theme-mode', mode)
      }, theme)
      await installProductionApi(page)

      await page.goto('/mobile/#/devices')
      await expect(page).toHaveURL(/\/mobile\/#\/devices$/)
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      await expectThemeChrome(page, theme)
      await expectNoHorizontalOverflow(page)

      await page.goto('/mobile/#/tasks')
      await expect(page).toHaveURL(/\/mobile\/#\/tasks$/)
      await expectNoHorizontalOverflow(page)
      expect(await page.evaluate(() => window.location.pathname)).toBe(
        '/mobile/',
      )
      expect(
        await page.evaluate(async () => {
          if (!('serviceWorker' in navigator)) return 0
          return (await navigator.serviceWorker.getRegistrations()).length
        }),
      ).toBe(0)
      expect(consoleErrors).toEqual([])
    })
  }
}
