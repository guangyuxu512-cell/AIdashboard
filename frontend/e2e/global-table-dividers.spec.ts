import { expect, test } from '@playwright/test'

for (const [theme, label] of [
  ['graphite', '石墨浅色'],
  ['forest', '森林绿'],
  ['coral', '珊瑚红'],
  ['midnight', '午夜青'],
]) {
  test(`global column dividers ${theme}: default shop, strategy and operating tables`, async ({
    page,
  }, info) => {
    const errors: string[] = [],
      external: string[] = []
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
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto('/#/shops')
    await page.getByRole('button', { name: '切换主题' }).click()
    await page.locator('.n-dropdown').getByText(label!, { exact: true }).click()
    await expect(page.locator('html')).toHaveAttribute(
      'data-theme-preset',
      theme!,
    )
    for (const [name, url] of [
      ['shops', '/#/shops'],
      ['strategies', '/#/product-selection'],
      ['operating', '/#/operating-dashboard'],
    ]) {
      await page.goto(url!)
      if (name === 'strategies')
        await page
          .getByRole('button', { name: '选品策略', exact: true })
          .click()
      const table =
        name === 'shops'
          ? page.locator('.shop-list-table .app-table')
          : name === 'operating'
            ? page.locator('.operating-dashboard-table .app-table')
            : page.locator('.selection-panel .app-table')
      if (name === 'strategies')
        await expect(
          table.getByRole('columnheader', { name: '策略名', exact: true }),
        ).toBeVisible()
      await expect(table.locator('.n-data-table-td').first()).toBeVisible()
      const borders = await table.evaluate((element) => {
        const header = getComputedStyle(element.querySelector('th')!),
          cell = getComputedStyle(element.querySelector('td')!)
        return {
          header: [header.borderRightWidth, header.borderRightStyle],
          body: [cell.borderRightWidth, cell.borderRightStyle],
          color: cell.borderRightColor,
          horizontalColor: cell.borderBottomColor,
          font: cell.fontSize,
        }
      })
      expect(borders.header).toEqual(['1px', 'solid'])
      expect(borders.body).toEqual(['1px', 'solid'])
      expect(borders.color).toBe(borders.horizontalColor)
      expect(borders.font).toBe('14px')
      const input = page.locator('.filter-bar .n-input').first()
      if (await input.count())
        expect(
          await input.evaluate(
            (element) => element.getBoundingClientRect().height,
          ),
        ).toBe(34)
      const action = table.getByRole('columnheader', {
        name: '操作',
        exact: true,
      })
      if (await action.count()) {
        const before = (await action.boundingBox())!.x
        const scroll = table.locator(
          '.n-data-table-base-table-body .n-scrollbar-container',
        )
        if (await scroll.count())
          await scroll.evaluate((element) => {
            element.scrollLeft = element.scrollWidth
          })
        expect(
          Math.abs((await action.boundingBox())!.x - before),
        ).toBeLessThanOrEqual(1)
      }
      if (name === 'shops') {
        await table
          .locator('.n-data-table-tbody [role="checkbox"]')
          .first()
          .click()
        await expect(table.locator('.app-table__row--selected')).toHaveCount(1)
      }
      await page.screenshot({
        path: info.outputPath(`${theme}-${name}-vertical-dividers.png`),
        animations: 'disabled',
      })
    }
    expect(external).toEqual([])
    expect(errors).toEqual([])
  })
}
