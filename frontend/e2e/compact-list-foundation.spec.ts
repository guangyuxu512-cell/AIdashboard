import { expect, test, type Locator } from '@playwright/test'

const themes = [
  ['graphite', '石墨浅色'],
  ['forest', '森林绿'],
  ['coral', '珊瑚红'],
  ['midnight', '午夜青'],
] as const
async function metrics(locator: Locator) {
  return locator.evaluate((element) => {
    const s = getComputedStyle(element),
      r = element.getBoundingClientRect()
    return {
      font: s.fontSize,
      height: r.height,
      width: r.width,
      padding: s.padding,
      gap: s.gap,
      color: s.color,
    }
  })
}

async function hoverLabel(locator: Locator) {
  await expect(locator).toBeVisible()
  const box = await locator.boundingBox()
  if (!box) throw new Error('Visible label has no bounds')
  // A tooltip can cover the label after mouseenter; do not repeatedly re-hover
  // its now-covered center while testing the resulting tooltip itself.
  await locator.page().mouse.move(box.x + 4, box.y + box.height / 2)
}

for (const [preset, label] of themes) {
  test(`${preset}: opt-in sizes, teleported menu and unchanged default consumers`, async ({
    page,
  }, info) => {
    const external: string[] = [],
      errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))
    await page.route('**/*', async (route) => {
      const url = new URL(route.request().url())
      if (
        url.origin === 'http://127.0.0.1:4176' &&
        !url.pathname.startsWith('/api/')
      )
        await route.continue()
      else {
        external.push(url.pathname)
        await route.abort()
      }
    })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto('/e2e/fixtures/list-density.html')
    await page.getByRole('button', { name: '切换主题' }).click()
    await page.locator('.n-dropdown').getByText(label, { exact: true }).click()
    await expect(page.locator('html')).toHaveAttribute(
      'data-theme-preset',
      preset,
    )
    await expect
      .poll(() => metrics(page.getByTestId('scoped-input')))
      .toMatchObject({
        font: '12px',
        height: 28,
      })
    expect(await metrics(page.getByTestId('scoped-primary'))).toMatchObject({
      font: '12px',
      height: 28,
    })
    expect(await metrics(page.getByTestId('scoped-reset'))).toMatchObject({
      font: '12px',
      height: 28,
    })
    expect(
      await metrics(
        page
          .getByTestId('scoped-filter')
          .locator('.filter-field > span')
          .first(),
      ),
    ).toMatchObject({ font: '13px' })
    await expect
      .poll(() => metrics(page.getByTestId('scoped-list')))
      .toMatchObject({
        padding: '12px',
        font: '12px',
      })
    expect(
      await metrics(page.locator('.management-list-section__content')),
    ).toMatchObject({ gap: '8px' })
    expect(
      await metrics(page.locator('.n-data-table-th').first()),
    ).toMatchObject({ font: '12px' })
    expect(
      await metrics(page.locator('.n-data-table-td').first()),
    ).toMatchObject({ font: '12px', padding: '8px 12px' })
    for (const image of await page.locator('.data-table .product-image').all())
      expect(await metrics(image)).toMatchObject({ width: 48, height: 48 })
    expect(
      await metrics(
        page.locator('.data-table .product-info-cell__id-text').first(),
      ),
    ).toMatchObject({ font: '12px' })
    expect(
      await metrics(
        page.locator('.data-table .product-info-cell__copy').first(),
      ),
    ).toMatchObject({ width: 28, height: 28 })
    expect(
      await metrics(page.locator('.n-pagination-item').first()),
    ).toMatchObject({ font: '12px', height: 28 })
    expect(await metrics(page.getByTestId('default-input'))).toMatchObject({
      font: '14px',
      height: 34,
    })
    expect(
      await metrics(
        page.getByTestId('default-consumer').locator('.product-image'),
      ),
    ).toMatchObject({ height: 64 })
    const rowHeight = (await metrics(page.locator('.n-data-table-tr').nth(1)))
      .height
    expect(rowHeight).toBeGreaterThanOrEqual(64)
    expect(rowHeight).toBeLessThanOrEqual(66)

    const select = page.getByTestId('scoped-select')
    await select.click()
    const menu = page.locator('.n-base-select-menu:visible')
    await expect(menu).toBeVisible()
    expect(
      await menu.evaluate(
        (element) =>
          !element.closest('.filter-bar--compact') &&
          !!element.closest('#app-overlay-host'),
      ),
    ).toBe(true)
    expect(
      await metrics(menu.locator('.n-base-select-option').first()),
    ).toMatchObject({ font: '12px', height: 28 })
    await hoverLabel(menu.locator('.app-select-label').last())
    const compactTooltip = page
      .locator('.n-tooltip:visible')
      .filter({ hasText: '提示-乙' })
    await expect(compactTooltip).toBeVisible()
    expect(await metrics(compactTooltip)).toMatchObject({
      font: '12px',
    })
    await page.keyboard.press('Escape')
    await page.mouse.move(1, 1)
    await select.locator('.n-base-clear').click()
    await expect(select).not.toContainText('提示-甲')
    await select.click()
    await page.keyboard.press('ArrowDown')
    await page.keyboard.press('Enter')
    await expect(select).toContainText('完整长店铺名称')
    await page.mouse.move(1, 1)
    await expect(page.locator('.n-tooltip:visible')).toHaveCount(0)

    await page.getByTestId('default-select').click()
    const defaultMenu = page.locator('.n-base-select-menu:visible')
    await expect
      .poll(() => metrics(defaultMenu.locator('.n-base-select-option').first()))
      .toMatchObject({ font: '14px', height: 34 })
    await page.keyboard.press('Escape')
    await page.mouse.move(1, 1)
    await expect(page.locator('.n-tooltip:visible')).toHaveCount(0)
    await hoverLabel(page.getByTestId('default-tooltip'))
    await expect(page.locator('.n-tooltip:visible')).toContainText(
      '未启用紧凑的提示',
    )
    expect(await metrics(page.locator('.n-tooltip:visible'))).toMatchObject({
      font: '14px',
    })
    await page.mouse.move(1, 1)
    await expect(page.locator('.n-tooltip:visible')).toHaveCount(0)
    await page.getByTestId('scoped-filter').click({ position: { x: 1, y: 1 } })
    await page.getByTestId('open-detail').click()
    const detail = page.getByTestId('default-detail')
    await expect(detail).toBeVisible()
    expect(await metrics(detail.locator('.app-field'))).toMatchObject({
      font: '14px',
      height: 34,
    })
    expect(
      await metrics(detail.locator('.product-image--summary')),
    ).toMatchObject({ height: 80 })
    expect(
      await metrics(detail.locator('.product-image--thumbnail')),
    ).toMatchObject({ height: 64 })
    expect(
      await metrics(detail.locator('.product-info-cell__id-text')),
    ).toMatchObject({ font: '13px' })
    await page.getByRole('button', { name: '关闭', exact: true }).click()
    await page.getByTestId('toggle-density').click()
    await expect
      .poll(() => metrics(page.getByTestId('scoped-input')))
      .toMatchObject({
        font: '14px',
        height: 34,
      })
    await expect
      .poll(() => metrics(page.getByTestId('scoped-list')))
      .toMatchObject({
        padding: '16px',
      })
    await page.getByTestId('scoped-select').click()
    await expect
      .poll(() =>
        metrics(
          page
            .locator('.n-base-select-menu:visible .n-base-select-option')
            .first(),
        ),
      )
      .toMatchObject({ font: '14px', height: 34 })
    await page.keyboard.press('Escape')
    await page.getByTestId('toggle-density').click()
    if (preset === 'graphite') {
      const virtual = page.getByTestId('virtual-select')
      await virtual.click()
      const virtualMenu = page.locator('.n-base-select-menu:visible')
      await expect(
        virtualMenu.getByText('第 1 项可选类目', { exact: true }),
      ).toBeVisible()
      expect(
        await virtualMenu.locator('.n-base-select-option').count(),
      ).toBeLessThan(80)
      await virtualMenu.locator('.n-virtual-list').evaluate((element) => {
        element.scrollTop = element.scrollHeight
      })
      const last = virtualMenu.getByText('第 80 项可选类目', { exact: true })
      await expect(last).toBeVisible()
      await expect
        .poll(() =>
          metrics(
            virtualMenu
              .locator('.n-base-select-option')
              .filter({ hasText: '第 80 项可选类目' }),
          ),
        )
        .toMatchObject({ height: 28 })
      await last.click()
      await expect(virtual).toContainText('第 80 项可选类目')
      await virtual.locator('.n-base-clear').click()
      await expect(virtual).not.toContainText('第 80 项可选类目')
      await virtual.click()
      await page.keyboard.press('ArrowDown')
      await page.keyboard.press('Enter')
      await expect(virtual).toContainText('可选类目')
    }
    await page.locator('.n-pagination .n-select').click()
    await expect
      .poll(() =>
        metrics(
          page
            .locator('.n-base-select-menu:visible .n-base-select-option')
            .first(),
        ),
      )
      .toMatchObject({ font: '12px', height: 28 })
    await page.keyboard.press('Escape')
    await expect(page.locator('.data-table img').first()).toBeVisible()
    await expect
      .poll(() =>
        page
          .locator('.data-table img')
          .first()
          .evaluate(
            (image: HTMLImageElement) =>
              image.complete && image.naturalWidth > 0,
          ),
      )
      .toBe(true)
    const imageSlot = page.locator('.data-table .product-image').first()
    await imageSlot.locator('img').dispatchEvent('error')
    await expect(
      imageSlot.getByRole('button', { name: '重试商品图片' }),
    ).toBeVisible()
    expect(await metrics(imageSlot)).toMatchObject({ width: 48, height: 48 })
    expect(await metrics(imageSlot.getByRole('button'))).toMatchObject({
      height: 28,
    })
    await imageSlot.getByRole('button').click()
    await expect
      .poll(() =>
        imageSlot
          .locator('img')
          .evaluate(
            (image: HTMLImageElement) =>
              image.complete && image.naturalWidth > 0,
          ),
      )
      .toBe(true)
    await page.screenshot({
      path: info.outputPath(`${preset}-scoped-foundation.png`),
      animations: 'disabled',
    })
    expect(external).toEqual([])
    expect(errors).toEqual([])
  })
}
