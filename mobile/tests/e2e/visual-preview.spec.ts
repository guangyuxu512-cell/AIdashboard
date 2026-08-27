import { expect, test, type Page } from '@playwright/test'

const viewportWidths = [360, 375, 390, 430] as const
const themes = ['light', 'dark'] as const

function observePage(page: Page) {
  const consoleErrors: string[] = []
  const consoleInfo: string[] = []
  const apiRequests: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
    if (message.type() === 'info') consoleInfo.push(message.text())
  })
  page.on('pageerror', (error) => consoleErrors.push(error.message))
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.startsWith('/api/')) {
      apiRequests.push(request.url())
    }
  })
  return { consoleErrors, consoleInfo, apiRequests }
}

async function setTheme(page: Page, theme: 'light' | 'dark'): Promise<void> {
  await page.addInitScript((mode) => {
    window.localStorage.setItem('control-center.mobile.theme-mode', mode)
  }, theme)
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

for (const width of viewportWidths) {
  for (const theme of themes) {
    test(`Visual Mock ${width}px ${theme} 稳定展示设备与任务`, async ({
      page,
    }, testInfo) => {
      const observation = observePage(page)
      await page.setViewportSize({ width, height: 844 })
      await setTheme(page, theme)
      await page.goto('/#/devices')

      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      await expect(page.getByTestId('device-card')).toHaveCount(20)
      await expect(page.getByTestId('summary-online')).toHaveText('4')
      await expect(page.getByTestId('summary-running')).toHaveText('0')
      await expect(page.getByTestId('summary-offline')).toHaveText('1')
      await expect(page.getByText('20 台', { exact: true })).toBeVisible()
      await expect(page.getByTestId('mobile-list-selector')).toContainText(
        '全部',
      )
      await expect(page.getByTestId('mobile-list-filter')).toContainText('筛选')
      await expect(page.getByText('加载失败', { exact: true })).toHaveCount(0)
      await expect(page.getByText('没有设备', { exact: true })).toHaveCount(0)

      const headerVisual = await page.evaluate(() => {
        const header = document.querySelector<HTMLElement>(
          '[data-testid="mobile-shell-header"]',
        )!
        const buttons = Array.from(
          document.querySelectorAll<HTMLElement>(
            '.mobile-global-header__actions .mobile-icon-button',
          ),
        )
        const buttonStyles = buttons.map((button) => {
          const box = button.getBoundingClientRect()
          const surface = window.getComputedStyle(button, '::before')
          return {
            width: box.width,
            height: box.height,
            background: surface.backgroundColor,
            shadow: surface.boxShadow,
          }
        })
        const headerStyle = window.getComputedStyle(header)
        return {
          borderBottomWidth: headerStyle.borderBottomWidth,
          boxShadow: headerStyle.boxShadow,
          buttonStyles,
          iconSources: Array.from(
            document.querySelectorAll<HTMLImageElement>(
              '.mobile-global-header__actions .mobile-header-icon',
            ),
          ).map((icon) => ({ src: icon.currentSrc, width: icon.naturalWidth })),
        }
      })
      expect(headerVisual.borderBottomWidth).toBe('0px')
      expect(headerVisual.boxShadow).toBe('none')
      expect(headerVisual.buttonStyles).toHaveLength(2)
      expect(headerVisual.buttonStyles[0]).toEqual(headerVisual.buttonStyles[1])
      expect(headerVisual.buttonStyles[0]?.width).toBeGreaterThanOrEqual(44)
      expect(headerVisual.iconSources).toHaveLength(2)
      expect(
        headerVisual.iconSources.every(
          (icon) =>
            (icon.src.includes('.svg') ||
              icon.src.startsWith('data:image/svg+xml')) &&
            icon.width > 0,
        ),
      ).toBe(true)

      const themeButton = page.getByTestId('theme-toggle')
      const bellButton = page.getByRole('button', { name: '通知' })
      expect((await themeButton.boundingBox())!.x).toBeLessThan(
        (await bellButton.boundingBox())!.x,
      )
      await expect(page.getByRole('tab')).toHaveText([
        '设备',
        '任务',
        '计划',
        '店铺',
        '我的',
      ])
      await expectNoHorizontalOverflow(page)
      expect(
        await page.evaluate(() => {
          const style = (selector: string) =>
            window.getComputedStyle(
              document.querySelector<HTMLElement>(selector)!,
            )
          const scroll = document.querySelector<HTMLElement>(
            '[data-testid="device-list-scroll"]',
          )!
          return {
            summaryHeight: style('.mobile-summary-strip').height,
            summaryInline: Array.from(
              document.querySelectorAll<HTMLElement>(
                '.mobile-summary-strip__item',
              ),
            ).every((item) => {
              const value = item.querySelector<HTMLElement>('dd')!
              const label = item.querySelector<HTMLElement>('dt')!
              const valueBox = value.getBoundingClientRect()
              const labelBox = label.getBoundingClientRect()
              return (
                valueBox.right <= labelBox.left &&
                Math.abs(valueBox.bottom - labelBox.bottom) <= 8
              )
            }),
            toolbarHeight: style('.mobile-list-toolbar').height,
            selectorVisualHeight: style(
              '[data-testid="mobile-list-selector"] .mobile-list-toolbar__control',
            ).height,
            scrollbarWidth: style('[data-testid="device-list-scroll"]')
              .scrollbarWidth,
            scrollable: scroll.scrollHeight > scroll.clientHeight,
            documentScrollTop: document.scrollingElement?.scrollTop ?? 0,
          }
        }),
      ).toEqual({
        summaryHeight: '64px',
        summaryInline: true,
        toolbarHeight: '44px',
        selectorVisualHeight: '32px',
        scrollbarWidth: 'none',
        scrollable: true,
        documentScrollTop: 0,
      })

      if (width === 390) {
        await page.screenshot({
          path: testInfo.outputPath(`visual-device-390-${theme}.png`),
        })
      }

      await page
        .getByRole('button', { name: '查看设备：运营', exact: true })
        .click()
      await expect(page).toHaveURL(/#\/devices\/visual-device-operations$/)
      await expect(page.getByTestId('device-summary-device')).toContainText(
        '运营',
      )
      await expect(page.getByTestId('device-summary-yingdao')).toContainText(
        'HuanYu001',
      )
      await expect(page.getByTestId('device-capability-panel')).toHaveCSS(
        'height',
        '200px',
      )
      const summaryColumns = await page
        .locator('.device-yingdao-summary__column')
        .evaluateAll((columns) =>
          columns.map((column) => {
            const box = column.getBoundingClientRect()
            return { x: box.x, y: box.y, width: box.width }
          }),
        )
      expect(summaryColumns).toHaveLength(2)
      expect(summaryColumns[0]!.y).toBe(summaryColumns[1]!.y)
      expect(summaryColumns[0]!.x).toBeLessThan(summaryColumns[1]!.x)
      expect(
        Math.abs(summaryColumns[0]!.width - summaryColumns[1]!.width),
      ).toBeLessThanOrEqual(1)
      await expectNoHorizontalOverflow(page)

      await page.goBack()
      await expect(page).toHaveURL(/#\/devices$/)

      await page.getByRole('tab', { name: /任务$/ }).click()
      await expect(page).toHaveURL(/#\/tasks$/)
      await expect(page.getByTestId('task-card')).toHaveCount(5)
      for (const status of ['执行中', '成功', '失败', '待执行', '已丢失']) {
        await expect(
          page.getByText(status, { exact: true }).first(),
        ).toBeVisible()
      }
      await expect(page.getByText('加载失败', { exact: true })).toHaveCount(0)
      await expect(page.getByText('暂无任务', { exact: true })).toHaveCount(0)
      await expectNoHorizontalOverflow(page)
      await expect(page.getByTestId('mobile-list-toolbar')).toHaveCSS(
        'height',
        '44px',
      )
      await expect(page.getByTestId('task-list-scroll')).toHaveCSS(
        'scrollbar-width',
        'none',
      )

      if (width === 390) {
        await page.screenshot({
          path: testInfo.outputPath(`visual-task-390-${theme}.png`),
        })
      }

      expect(observation.apiRequests).toEqual([])
      expect(observation.consoleErrors).toEqual([])
      expect(
        observation.consoleInfo.some((message) =>
          message.includes('Mock DataSource enabled'),
        ),
      ).toBe(true)
    })
  }
}

test('Visual Mock 复用正式设备详情与任务详情', async ({ page }, testInfo) => {
  const observation = observePage(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await setTheme(page, 'light')
  await page.goto('/#/devices')
  await expect(page.getByTestId('device-card')).toHaveCount(20)

  await page
    .getByRole('button', { name: '查看设备：运营', exact: true })
    .click()
  await expect(page).toHaveURL(/#\/devices\/visual-device-operations$/)
  await expect(page.getByTestId('device-detail')).toContainText('运营')
  await expect(page.getByTestId('device-summary-device')).toContainText(
    '运营在线已启用Worker 0.4.6',
  )
  await expect(page.getByTestId('device-summary-yingdao')).toContainText(
    '影刀账号HuanYu001就绪6.3.6',
  )
  await expect(page.getByTestId('device-capability-tabs')).toContainText(
    '影刀应用 8Skills 5',
  )
  await expect(page.getByTestId('device-current-task')).toContainText(
    '订单同步',
  )
  await expect(
    page.getByRole('region', { name: '设备详情内容' }),
  ).toHaveAttribute('tabindex', '0')
  const layout = await page.evaluate(() => {
    const list = document.querySelector<HTMLElement>(
      '[data-testid="application-list"]',
    )!
    const rows = Array.from(
      list.querySelectorAll<HTMLElement>('[data-testid="application-row"]'),
    )
    const listBox = list.getBoundingClientRect()
    return {
      panelHeight: document
        .querySelector<HTMLElement>('[data-testid="device-capability-panel"]')!
        .getBoundingClientRect().height,
      rowHeights: rows
        .slice(0, 4)
        .map((row) => row.getBoundingClientRect().height),
      threeRowsVisible: rows
        .slice(0, 3)
        .every(
          (row) => row.getBoundingClientRect().bottom <= listBox.bottom + 1,
        ),
      fourthRequiresScroll:
        rows[3]!.getBoundingClientRect().bottom > listBox.bottom + 1,
      listScrollable: list.scrollHeight > list.clientHeight,
      listScrollbarWidth: window.getComputedStyle(list).scrollbarWidth,
      detailScrollbarWidth: window.getComputedStyle(
        document.querySelector<HTMLElement>('.app-page')!,
      ).scrollbarWidth,
    }
  })
  expect(layout).toEqual({
    panelHeight: 200,
    rowHeights: [44, 44, 44, 44],
    threeRowsVisible: true,
    fourthRequiresScroll: true,
    listScrollable: true,
    listScrollbarWidth: 'none',
    detailScrollbarWidth: 'none',
  })
  await expect(
    page.getByText('visual-app-orders', { exact: true }),
  ).toHaveCount(0)
  await expect(
    page.getByText('visual-device-operations', { exact: true }),
  ).toBeHidden()
  await expect(page.getByRole('button', { name: /配置：拼多多/ })).toBeVisible()
  await expect(page.getByRole('button', { name: /运行：拼多多/ })).toBeVisible()
  await page.screenshot({
    path: testInfo.outputPath('visual-device-detail-390-light.png'),
  })

  const applicationList = page.getByTestId('application-list')
  await applicationList.evaluate((element) => {
    element.scrollTop = element.scrollHeight
  })
  await expect
    .poll(() => applicationList.evaluate((element) => element.scrollTop))
    .toBeGreaterThan(0)
  await page.screenshot({
    path: testInfo.outputPath('visual-device-capability-scroll-390-light.png'),
  })

  await page.getByRole('tab', { name: 'Skills 5' }).click()
  await expect(page.getByTestId('skill-row')).toHaveCount(5)
  await expect(page.getByText('运行状态检查', { exact: true })).toHaveCount(0)
  await expect(
    page.getByRole('button', { name: '配置：订单同步' }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: '运行：库存同步' }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: '配置：库存同步' }),
  ).toHaveCount(0)
  await page.screenshot({
    path: testInfo.outputPath('visual-device-skills-390-light.png'),
  })

  await page.getByText('更多信息', { exact: true }).click()
  const detailScroll = page.getByRole('region', { name: '设备详情内容' })
  await page.getByRole('tab', { name: '影刀应用 8' }).click()
  await detailScroll.evaluate((element) => {
    element.scrollTop = 0
  })
  await applicationList.evaluate((element) => {
    element.scrollTop = element.scrollHeight
  })
  await applicationList.hover()
  await page.mouse.wheel(0, 800)
  await expect
    .poll(() => detailScroll.evaluate((element) => element.scrollTop))
    .toBeGreaterThan(0)

  await page.getByRole('button', { name: '查看任务：订单同步' }).click()
  await expect(page).toHaveURL(
    /#\/tasks\/visual-task-running\?fromDeviceId=visual-device-operations$/,
  )
  await expect(page.getByTestId('task-detail')).toContainText('订单同步')
  await expect(page.getByTestId('detail-progress-value')).toHaveText('3 / 5')
  await expect(page.getByTestId('runtime-events')).toContainText(
    '正在处理 HuanYu 店铺',
  )
  await page.screenshot({
    path: testInfo.outputPath('visual-task-detail-390-light.png'),
  })

  expect(observation.apiRequests).toEqual([])
  expect(observation.consoleErrors).toEqual([])
})
