import { expect, test } from '@playwright/test'

test.skip(process.env.PLAYWRIGHT_API_MODE === 'real', 'Mock mode coverage')

async function expectOfficeReady(page: import('@playwright/test').Page) {
  const office = page.getByTestId('device-office-stage')
  await expect(office).toBeVisible()
  await expect(office).toHaveAttribute('data-stage-mode', 'ready')
  await expect(office).toHaveAttribute('data-asset-version', '2.0')
  return office
}

test('renders official 2.5D layers, states, drawer and list view', async ({
  page,
}) => {
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))

  await page.goto('/#/devices')
  await page.getByLabel('切换主题').click()
  await page.getByText('深色', { exact: true }).click()
  const office = await expectOfficeReady(page)

  await expect(
    office.locator('[data-office-layer="01-background"]'),
  ).toHaveCount(1)
  await expect(office.locator('.workstation-slot')).toHaveCount(9)
  await expect(
    office.locator('[data-office-layer="02-desk-base"]'),
  ).toHaveCount(9)
  await expect(
    office.locator('[data-office-layer="05-foreground-mask"]'),
  ).toHaveCount(9)
  await expect(office.getByText('REFERENCE_PREVIEW')).toHaveCount(0)
  await expect(office.getByText('ART ASSETS PENDING')).toHaveCount(0)

  const onlineSlot = office.getByTestId('office-slot-1')
  await expect(onlineSlot).toHaveAttribute('data-visual-state', 'onlineIdle')
  await expect(
    onlineSlot.locator('[data-office-layer="04-actor"] img'),
  ).toHaveAttribute('src', /actor-idle-aligned\.png/)
  await expect(
    onlineSlot.locator('[data-office-layer="03-screen-overlay"] img'),
  ).toHaveAttribute('src', /screen-idle-aligned\.webp/)

  const offlineSlot = office.getByTestId('office-slot-4')
  await expect(
    offlineSlot.locator('[data-office-layer="04-actor"] img'),
  ).toHaveAttribute('src', /actor-sleep-aligned\.png/)
  await expect(
    offlineSlot.locator('[data-office-layer="07-fx-overlay"] img'),
  ).toHaveAttribute('src', /zzz\.png/)

  const errorSlot = office.getByTestId('office-slot-5')
  await expect(
    errorSlot.locator('[data-office-layer="04-actor"] img'),
  ).toHaveAttribute('src', /actor-error-aligned\.png/)
  await expect(
    errorSlot.locator('[data-office-layer="07-fx-overlay"] img'),
  ).toHaveAttribute('src', /warning\.png/)

  await page.getByRole('button', { name: '查看设备 杭州-运营机-01' }).click()
  await expect(page.getByText('设备详情', { exact: true })).toBeVisible()
  await expect(
    page.getByText('device-fixture-001', { exact: true }),
  ).toBeVisible()
  await expect(page.getByText('CPU 摘要', { exact: true })).toHaveCount(0)
  await expect(page.getByText('内存摘要', { exact: true })).toHaveCount(0)
  await expect(page.getByText('执行关系', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '关闭' }).click()

  await page.getByRole('button', { name: '列表' }).click()
  await expect(
    page.getByRole('columnheader', { name: '设备名称' }),
  ).toBeVisible()
  await expect(page.getByTestId('device-office-stage')).toHaveCount(0)
  await page.getByRole('button', { name: '办公区' }).click()
  await expectOfficeReady(page)

  const overflow = await page.evaluate(() => ({
    document:
      document.documentElement.scrollWidth >
      document.documentElement.clientWidth,
    body: document.body.scrollWidth > document.body.clientWidth,
  }))
  expect(overflow).toEqual({ document: false, body: false })
  expect(runtimeErrors).toEqual([])
})

test('uses identical V2 station geometry across light and dark themes', async ({
  page,
}) => {
  await page.goto('/#/devices')
  await page.getByLabel('切换主题').click()
  await page.getByText('浅色', { exact: true }).click()
  const office = await expectOfficeReady(page)
  const lightGeometry = await office
    .locator('.workstation-slot')
    .evaluateAll((slots) =>
      slots.map((slot) => {
        const style = getComputedStyle(slot)
        return [style.left, style.top, style.width, style.height]
      }),
    )
  await expect(office.getByTestId('office-slot-1')).toHaveAttribute(
    'data-desk-asset',
    /desk-light-base\.webp/,
  )
  await expect(office.getByTestId('office-slot-1')).toHaveAttribute(
    'data-mask-asset',
    /desk-foreground-mask-light\.webp/,
  )

  await page.getByLabel('切换主题').click()
  await page.getByText('深色', { exact: true }).click()
  await expectOfficeReady(page)
  const darkGeometry = await office
    .locator('.workstation-slot')
    .evaluateAll((slots) =>
      slots.map((slot) => {
        const style = getComputedStyle(slot)
        return [style.left, style.top, style.width, style.height]
      }),
    )
  expect(darkGeometry).toEqual(lightGeometry)
  await expect(office.getByTestId('office-slot-1')).toHaveAttribute(
    'data-desk-asset',
    /desk-dark-base\.webp/,
  )
  await expect(office.getByTestId('office-slot-1')).toHaveAttribute(
    'data-mask-asset',
    /desk-foreground-mask-dark\.webp/,
  )

  await page.getByLabel('切换主题').click()
  await page.getByText('跟随系统', { exact: true }).click()
  await expectOfficeReady(page)
  const systemGeometry = await office
    .locator('.workstation-slot')
    .evaluateAll((slots) =>
      slots.map((slot) => {
        const style = getComputedStyle(slot)
        return [style.left, style.top, style.width, style.height]
      }),
    )
  expect(systemGeometry).toEqual(lightGeometry)
})

test('renders zero, one and paginated device projections without fake devices', async ({
  page,
}) => {
  await page.goto('/#/devices')
  const office = await expectOfficeReady(page)
  const search = page.getByRole('textbox', { name: '搜索当前页设备' })

  await search.fill('不存在的设备')
  await expect(office.locator('.workstation-slot.is-empty')).toHaveCount(9)
  await expect(
    office.locator('[data-office-layer="02-desk-base"]'),
  ).toHaveCount(9)
  await expect(
    office.locator('[data-office-layer="05-foreground-mask"]'),
  ).toHaveCount(9)
  await expect(office.locator('[data-office-layer="04-actor"]')).toHaveCount(0)
  await expect(
    office.locator('[data-office-layer="03-screen-overlay"]'),
  ).toHaveCount(0)
  await expect(
    office.locator('[data-office-layer="07-fx-overlay"]'),
  ).toHaveCount(0)

  await search.fill('杭州-运营机-01')
  await expect(office.locator('[data-office-layer="04-actor"]')).toHaveCount(1)
  await expect(office.locator('.workstation-slot.is-empty')).toHaveCount(8)

  await search.fill('')
  await page
    .locator('.pagination-bar .n-pagination-item')
    .filter({ hasText: '2' })
    .click()
  await expect(page.getByRole('button', { name: /查看设备/ })).toHaveCount(2)
  await expect(page.getByRole('button', { name: /空工位/ })).toHaveCount(7)
})

for (const viewport of [
  { width: 1920, height: 1080 },
  { width: 1440, height: 900 },
  { width: 1366, height: 768 },
]) {
  test(`keeps the complete office usable within ${viewport.width}×${viewport.height}`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport)
    await page.goto('/#/devices')
    const office = await expectOfficeReady(page)
    await expect(
      page.getByRole('button', { name: '查看设备 杭州-运营机-01' }),
    ).toBeVisible()

    const bounds = await office.boundingBox()
    expect(bounds).not.toBeNull()
    expect(bounds!.width).toBeLessThanOrEqual(viewport.width)
    expect(bounds!.height).toBeGreaterThan(400)
  })
}
