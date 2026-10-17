import { expect, test } from '@playwright/test'
import { PRODUCT_ID_LENGTH_FIXTURE } from '../src/features/product-data/fixtures/product-id-lengths.fixture'

for (const [width, height] of [
  [1024, 768],
  [1440, 900],
  [1920, 1080],
]) {
  test(
    'aligns mixed-length product ID copy buttons at ' + width,
    async ({ page }, info) => {
      await page.setViewportSize({ width, height })
      await page.goto('/#/product-data?productDataPreview=mixed-ids')
      await page
        .context()
        .grantPermissions(['clipboard-read', 'clipboard-write'])
      const rows = page.locator(
        '.product-data-table .n-data-table-tbody .n-data-table-tr',
      )
      await expect(rows).toHaveCount(20)
      await page.evaluate(async () => {
        await document.fonts.ready
        await Promise.all(
          Array.from(document.images).map((image) =>
            image.decode().catch(() => undefined),
          ),
        )
      })
      const geometry = () =>
        rows.evaluateAll((items) =>
          items.slice(0, 3).map((row) => {
            const cell = row.querySelector<HTMLElement>('.product-info-cell')!
            const line = cell.querySelector<HTMLElement>(
              '.product-info-cell__id',
            )!
            const text = line.querySelector<HTMLElement>('span')!
            const button = line.querySelector<HTMLButtonElement>('button')!
            const image = cell.querySelector<HTMLImageElement>('img')!
            const title = cell.querySelector<HTMLElement>(
              '.product-info-cell__title',
            )!
            const range = document.createRange()
            range.selectNodeContents(title)
            const textArea = cell
              .querySelector<HTMLElement>('.product-info-cell__text')!
              .getBoundingClientRect()
            const buttonBounds = button.getBoundingClientRect(),
              lineBounds = line.getBoundingClientRect()
            return {
              copyX: buttonBounds.x,
              copyWidth: buttonBounds.width,
              lineX: lineBounds.x,
              lineWidth: lineBounds.width,
              textWidth: text.getBoundingClientRect().width,
              clipped: text.scrollWidth > text.clientWidth,
              textAreaWidth: textArea.width,
              buttonVisible:
                buttonBounds.x >= textArea.x &&
                buttonBounds.right <= textArea.right &&
                buttonBounds.width > 0,
              rowHeight: row.getBoundingClientRect().height,
              titleLines: new Set(
                Array.from(range.getClientRects()).map((rect) =>
                  Math.round(rect.top),
                ),
              ).size,
              imageWidth: image.getBoundingClientRect().width,
              imageHeight: image.getBoundingClientRect().height,
            }
          }),
        )
      const metrics = await geometry()
      console.log('PRODUCT_ID_ALIGNMENT', JSON.stringify({ width, metrics }))
      expect(
        Math.max(...metrics.map((item) => item.copyX)) -
          Math.min(...metrics.map((item) => item.copyX)),
      ).toBeLessThanOrEqual(0.5)
      expect(
        Math.max(...metrics.map((item) => item.textWidth)) -
          Math.min(...metrics.map((item) => item.textWidth)),
      ).toBeLessThanOrEqual(0.5)
      expect(metrics[1]!.clipped).toBe(false)
      expect(metrics[2]!.clipped).toBe(true)
      for (const item of metrics) {
        expect(item.buttonVisible).toBe(true)
        expect(item.copyWidth).toBe(28)
        expect(item.lineWidth).toBeLessThanOrEqual(192)
        expect(item.titleLines).toBe(1)
        expect(item.rowHeight).toBe(65)
        expect(item.imageWidth).toBe(48)
        expect(item.imageHeight).toBe(48)
      }
      for (const [index, id] of PRODUCT_ID_LENGTH_FIXTURE.entries()) {
        await expect(
          rows.nth(index).locator('.product-info-cell__id > span'),
        ).toHaveText('ID：' + id)
        await rows
          .nth(index)
          .getByRole('button', { name: '复制商品ID', exact: true })
          .click()
        expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(
          id,
        )
      }
      await page.mouse.move(0, 0)
      await expect(page.locator('.n-tooltip:visible')).toHaveCount(0)
      await expect(page.locator('.n-message')).toHaveCount(0)
      await page.screenshot({
        path: info.outputPath('copy-alignment-' + width + '.png'),
        animations: 'disabled',
      })
      const longId = rows.nth(2).locator('.product-info-cell__id-text')
      await longId.hover()
      const fullId = page
        .locator('.n-tooltip')
        .filter({ hasText: 'ID：' + PRODUCT_ID_LENGTH_FIXTURE[2] })
      await expect(fullId).toBeVisible()
      await expect(fullId).toHaveCSS('opacity', '1')
      const popupBounds = await fullId.boundingBox()
      expect(popupBounds!.x).toBeGreaterThanOrEqual(0)
      expect(popupBounds!.x + popupBounds!.width).toBeLessThanOrEqual(width)
      await page.screenshot({
        path: info.outputPath('copy-alignment-full-id-' + width + '.png'),
        animations: 'disabled',
      })
      await page.mouse.move(0, 0)
      await expect(fullId).not.toBeVisible()
      await rows.evaluateAll((items) =>
        items.slice(0, 3).forEach((row) => {
          // Isolated stress case only: constrain the ID line, not the table column.
          row.querySelector<HTMLElement>(
            '.product-info-cell__id',
          )!.style.width = '140px'
        }),
      )
      const constrained = await geometry()
      console.log(
        'PRODUCT_ID_ALIGNMENT_CONSTRAINED',
        JSON.stringify({ width, metrics: constrained }),
      )
      expect(
        Math.max(...constrained.map((item) => item.copyX)) -
          Math.min(...constrained.map((item) => item.copyX)),
      ).toBeLessThanOrEqual(0.5)
      for (const item of constrained) {
        expect(item.buttonVisible).toBe(true)
        expect(item.copyWidth).toBe(28)
        expect(item.lineWidth).toBe(140)
        expect(item.textWidth).toBeLessThan(160)
      }
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
      ).toBe(false)
    },
  )
}
