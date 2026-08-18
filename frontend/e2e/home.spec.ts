import { expect, test } from '@playwright/test'

test('shows the stage placeholder', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('阶段 0A 工程骨架已就绪。')).toBeVisible()
})
