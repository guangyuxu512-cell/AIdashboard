import { expect, test } from '@playwright/test'

for (const [width, height] of [
  [1024, 768],
  [1440, 900],
  [1920, 1080],
]) {
  test(
    'keeps long product titles on one line at ' + width,
    async ({ page }, info) => {
      await page.setViewportSize({ width, height })
      await page.goto('/#/product-data')
      const rows = page.locator(
        '.product-data-table .n-data-table-tbody .n-data-table-tr',
      )
      await expect(rows.first()).toBeVisible()
      await page.evaluate(async () => {
        await document.fonts.ready
        await Promise.all(
          Array.from(document.images).map((image) =>
            image.decode().catch(() => undefined),
          ),
        )
      })
      const metrics = await rows.first().evaluate((row) => {
        const cell = row.querySelector<HTMLElement>('.product-info-cell')!
        const text = cell.querySelector<HTMLElement>(
          '.product-info-cell__text',
        )!
        const title = text.querySelector<HTMLElement>('.n-ellipsis')!
        const id = cell.querySelector<HTMLElement>('.product-info-cell__id')!
        const image = cell.querySelector<HTMLImageElement>('img')!
        const shortRow = row.parentElement!.children[1]!
        const range = document.createRange()
        range.selectNodeContents(title)
        const style = getComputedStyle(title)
        return {
          longRowHeight: row.getBoundingClientRect().height,
          shortRowHeight: shortRow.getBoundingClientRect().height,
          productColumnWidth: cell.closest('td')!.getBoundingClientRect().width,
          titleLineCount: new Set(
            Array.from(range.getClientRects()).map((rect) =>
              Math.round(rect.top),
            ),
          ).size,
          titleHeight: title.getBoundingClientRect().height,
          lineHeight: Number.parseFloat(style.lineHeight),
          whiteSpace: style.whiteSpace,
          textOverflow: style.textOverflow,
          titleWidth: title.getBoundingClientRect().width,
          containerWidth: text.getBoundingClientRect().width,
          clipped: title.scrollWidth > title.clientWidth,
          idOnOwnLine:
            id.getBoundingClientRect().top >=
            title.getBoundingClientRect().bottom - 0.5,
          imageWidth: image.getBoundingClientRect().width,
          imageHeight: image.getBoundingClientRect().height,
          documentOverflow: document.documentElement.scrollWidth > innerWidth,
        }
      })
      await info.attach('title-geometry-' + width, {
        body: JSON.stringify(metrics, null, 2),
        contentType: 'application/json',
      })
      console.log(
        'PRODUCT_TITLE_GEOMETRY',
        JSON.stringify({ width, height, ...metrics }),
      )
      expect(metrics.titleLineCount).toBe(1)
      expect(metrics.whiteSpace).toBe('nowrap')
      expect(metrics.textOverflow).toBe('ellipsis')
      expect(metrics.titleHeight).toBeLessThanOrEqual(metrics.lineHeight + 0.5)
      expect(
        Math.abs(metrics.longRowHeight - metrics.shortRowHeight),
      ).toBeLessThanOrEqual(0.5)
      expect(metrics.titleWidth).toBeLessThanOrEqual(
        metrics.containerWidth + 0.5,
      )
      expect(metrics.clipped).toBe(true)
      expect(metrics.idOnOwnLine).toBe(true)
      expect(metrics.imageWidth).toBe(64)
      expect(metrics.imageHeight).toBe(64)
      expect(metrics.documentOverflow).toBe(false)

      const title = rows
        .first()
        .locator('.product-info-cell__text > .n-ellipsis')
      const fullTitle = (await title.textContent())!.trim()
      await expect(
        rows.first().locator('.product-info-cell__id > span'),
      ).toHaveText('ID：9000000000000000001')
      await title.hover()
      await expect(
        page.locator('.n-tooltip').filter({ hasText: fullTitle }),
      ).toBeVisible()
      await page.screenshot({
        path: info.outputPath('single-line-title-tooltip-' + width + '.png'),
        animations: 'disabled',
      })
      await page.mouse.move(0, 0)
      await expect(
        page.locator('.n-tooltip').filter({ hasText: fullTitle }),
      ).not.toBeVisible()
      await rows
        .first()
        .getByRole('button', { name: '复制商品ID', exact: true })
        .click()
      expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(
        '9000000000000000001',
      )
      await page.mouse.move(0, 0)
      await expect(page.locator('.n-tooltip:visible')).toHaveCount(0)
      await page.screenshot({
        path: info.outputPath('single-line-title-' + width + '.png'),
        animations: 'disabled',
      })
    },
  )
}
