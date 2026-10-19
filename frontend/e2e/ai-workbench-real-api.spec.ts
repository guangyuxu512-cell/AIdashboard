import { readFile } from 'node:fs/promises'
import { resolve, sep } from 'node:path'

import { expect, test, type Locator, type Page } from '@playwright/test'

import type {
  GenerationItemReadDto,
  GenerationJobReadDto,
  ProductMaterialGroupReadDto,
  TemplateGroupReadDto,
} from '../src/entities/ai-workbench'

test.skip(
  process.env.PLAYWRIGHT_API_MODE !== 'real',
  'Intercepted Real API UI contract coverage',
)

test.beforeEach(async ({ page }) => {
  if (process.env.PLAYWRIGHT_AI_STATIC !== '1') return
  const dist = resolve('dist')
  await page.route('**/*', async (route) => {
    const url = new URL(route.request().url())
    if (
      url.origin !== 'https://ai-images.test' ||
      url.pathname.startsWith('/api/')
    ) {
      await route.fulfill({
        status: 500,
        body: 'Unhandled controlled test request',
      })
      return
    }
    const file = resolve(
      dist,
      `.${decodeURIComponent(url.pathname === '/' ? '/index.html' : url.pathname)}`,
    )
    if (!file.startsWith(`${dist}${sep}`))
      throw new Error('Invalid static asset path')
    const extension = file.split('.').at(-1) ?? ''
    const contentType =
      {
        html: 'text/html',
        js: 'text/javascript',
        css: 'text/css',
        svg: 'image/svg+xml',
        png: 'image/png',
        woff2: 'font/woff2',
      }[extension] ?? 'application/octet-stream'
    await route.fulfill({ contentType, body: await readFile(file) })
  })
})

const modelId = '11111111-1111-4111-8111-111111111111'
const defaultTeamId = '00000000-0000-4000-8000-000000000021'
const shopeeTeamId = '00000000-0000-4000-8000-000000000022'
const alternateModelId = '11111111-1111-4111-8111-111111111112'
const groupId = '22222222-2222-4222-8222-222222222222'
const detailGroupId = '22222222-2222-4222-8222-222222222223'
const templateId = '33333333-3333-4333-8333-333333333333'
const detailTemplateId = '33333333-3333-4333-8333-333333333334'
const materialGroupId = '44444444-4444-4444-8444-444444444444'
const secondMaterialGroupId = '44444444-4444-4444-8444-444444444445'
const inputAssetId = '55555555-5555-4555-8555-555555555555'
const secondInputAssetId = '55555555-5555-4555-8555-555555555556'
const generatedProductAssetId = '55555555-5555-4555-8555-555555555557'
const supplementalInputAssetId = '55555555-5555-4555-8555-555555555558'
const generatedProductAssetIds = [
  generatedProductAssetId,
  '55555555-5555-4555-8555-555555555559',
  '55555555-5555-4555-8555-555555555560',
  '55555555-5555-4555-8555-555555555561',
  '55555555-5555-4555-8555-555555555562',
  '55555555-5555-4555-8555-555555555563',
  '55555555-5555-4555-8555-555555555564',
  '55555555-5555-4555-8555-555555555565',
] as const
const generatedProductAssetHashes = [
  'd',
  'e',
  'f',
  '1',
  '2',
  '3',
  '4',
  '5',
] as const
const jobId = '66666666-6666-4666-8666-666666666666'
const itemId = '77777777-7777-4777-8777-777777777777'
const outputAssetId = '88888888-8888-4888-8888-888888888888'
const timestamp = '2026-09-06T00:00:00Z'
const controlledAssetImage = `
  <svg xmlns="http://www.w3.org/2000/svg" width="512" height="384" viewBox="0 0 512 384">
    <defs>
      <linearGradient id="background" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#e8f3ff" />
        <stop offset="1" stop-color="#8eb8e8" />
      </linearGradient>
    </defs>
    <rect width="512" height="384" fill="url(#background)" />
    <rect x="150" y="82" width="212" height="220" rx="28" fill="#ffffff" />
    <rect x="178" y="124" width="156" height="18" rx="9" fill="#5b86b9" />
    <rect x="178" y="158" width="114" height="14" rx="7" fill="#9cb8d8" />
    <circle cx="256" cy="225" r="44" fill="#3b6fa8" />
    <text x="256" y="348" text-anchor="middle" fill="#1d426c" font-family="sans-serif" font-size="20">AI Output</text>
  </svg>
`

type ControlledJobStatus = 'PENDING' | 'RUNNING' | 'SUCCESS' | 'PARTIAL_FAILED'

interface WorkbenchApiOptions {
  controlledJob?: boolean
  submissionGate?: Promise<void>
  batchScenario?: boolean
  assetContentGate?: Promise<void>
  failAssetContentRequests?: number
  imageSize?: readonly [number, number]
  aiOnly?: boolean
  failUploadName?: string
  failAttach?: boolean
  failCleanup?: boolean
  superAccount?: boolean
  singleTeam?: boolean
  uploadGate?: Promise<void>
}

async function switchTeamContext(page: Page, label: string): Promise<void> {
  await page.getByRole('button', { name: '当前用户菜单' }).click()
  await page.getByText(label, { exact: true }).click()
}

test('Team context: super can browse globally and switch default, global and shopee with matching uploads', async ({
  page,
}) => {
  const calls = await installWorkbenchApi(page, { superAccount: true })
  const uploadTeams: Array<string | undefined> = []
  page.on('request', (request) => {
    if (
      new URL(request.url()).pathname === '/api/v1/ai-workbench/assets' &&
      request.method() === 'POST'
    )
      uploadTeams.push(request.headers()['x-team-id'])
  })
  await page.goto('/#/ai-workbench/assets')
  await expect(
    page.getByText('全部团队仅供浏览', { exact: false }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: '上传素材', exact: true }),
  ).toBeDisabled()
  await expect(
    page.getByRole('button', { name: '新建产品', exact: true }),
  ).toBeDisabled()
  await expect(
    page.getByRole('button', {
      name: `选择产品 ${secondMaterialGroup.name}`,
      exact: true,
    }),
  ).toBeVisible()
  await switchTeamContext(page, '切换至 默认团队')
  await expect(
    page.getByRole('button', {
      name: `选择产品 ${materialGroup.name}`,
      exact: true,
    }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', {
      name: `选择产品 ${secondMaterialGroup.name}`,
      exact: true,
    }),
  ).toHaveCount(0)
  await expect(
    page.getByRole('button', { name: '上传素材', exact: true }),
  ).toBeEnabled()
  await switchTeamContext(page, '切换至全部团队')
  await expect(
    page.getByRole('button', {
      name: `选择产品 ${secondMaterialGroup.name}`,
      exact: true,
    }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: '上传素材', exact: true }),
  ).toBeDisabled()
  await switchTeamContext(page, '切换至 shopee')
  await expect(
    page.getByRole('button', {
      name: `选择产品 ${materialGroup.name}`,
      exact: true,
    }),
  ).toHaveCount(0)
  await expect(
    page.getByRole('button', {
      name: `选择产品 ${secondMaterialGroup.name}`,
      exact: true,
    }),
  ).toBeVisible()
  await page.getByLabel('上传素材', { exact: true }).setInputFiles({
    name: 'shopee.png',
    mimeType: 'image/png',
    buffer: Buffer.from(proportionImage([400, 600])),
  })
  await expect(
    page.getByRole('button', { name: '查看素材 shopee.png', exact: true }),
  ).toBeVisible()
  expect(uploadTeams).toEqual([shopeeTeamId])
  expect(calls.materialAttachRequests()).toEqual([
    `/api/v1/ai-workbench/product-material-groups/${secondMaterialGroupId}/assets`,
  ])
})

test('Team context: a single-team super can return to global and retain it after reload', async ({
  page,
}) => {
  await installWorkbenchApi(page, { superAccount: true, singleTeam: true })
  await page.goto('/#/ai-workbench/assets')
  await switchTeamContext(page, '切换至 默认团队')
  await expect(
    page.getByRole('button', { name: '上传素材', exact: true }),
  ).toBeEnabled()
  await switchTeamContext(page, '切换至全部团队')
  await page.reload()
  await expect(
    page.getByText('全部团队仅供浏览', { exact: false }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: '上传素材', exact: true }),
  ).toBeDisabled()
})

test('Team context: global AI templates are readable but cannot be changed and generation requires a team', async ({
  page,
}) => {
  const calls = await installWorkbenchApi(page, {
    superAccount: true,
    controlledJob: true,
    batchScenario: true,
  })
  calls.setControlledJobStatus('PARTIAL_FAILED')
  await page.goto('/#/ai-workbench/templates')
  const createButtons = page.getByRole('button', {
    name: '新建模板组',
    exact: true,
  })
  await expect(createButtons).toHaveCount(2)
  for (const button of await createButtons.all())
    await expect(button).toBeDisabled()
  await expect(
    page.getByRole('button', { name: '添加模板', exact: true }),
  ).toHaveCount(0)
  await expect(
    page.getByRole('switch', { name: '模板组启用', exact: true }),
  ).toBeDisabled()
  await page
    .getByRole('navigation', { name: 'AI 功能入口' })
    .getByRole('button', { name: 'AI生图', exact: true })
    .click()
  await expect(
    page.getByText('请选择团队后使用生图', { exact: true }),
  ).toBeVisible()
  await expect(page.getByLabel('提示词', { exact: true })).toHaveCount(0)
  await page
    .getByRole('navigation', { name: 'AI 功能入口' })
    .getByRole('button', { name: '生成记录', exact: true })
    .click()
  await page
    .getByLabel('生成记录列表')
    .getByRole('button', { name: '查看', exact: true })
    .click()
  await expect(
    page.getByRole('button', { name: '重试失败项', exact: true }),
  ).toBeDisabled()
  expect(calls.retryBody()).toBeNull()
  await switchTeamContext(page, '切换至 默认团队')
  await expect(page.getByRole('dialog')).toHaveCount(0)
})

test('Team context: changing team while an upload finishes never attaches or cleans up in the next team', async ({
  page,
}) => {
  const gate = releaseGate()
  const calls = await installWorkbenchApi(page, {
    superAccount: true,
    uploadGate: gate.promise,
  })
  try {
    await page.goto('/#/ai-workbench/assets')
    await switchTeamContext(page, '切换至 默认团队')
    await expect(
      page.getByRole('button', { name: '上传素材', exact: true }),
    ).toBeEnabled()
    await page.getByLabel('上传素材', { exact: true }).setInputFiles({
      name: 'pending.png',
      mimeType: 'image/png',
      buffer: Buffer.from(proportionImage([400, 600])),
    })
    await expect.poll(calls.uploadCount).toBe(1)
    await switchTeamContext(page, '切换至 shopee')
    await expect(
      page.getByRole('button', {
        name: `选择产品 ${secondMaterialGroup.name}`,
        exact: true,
      }),
    ).toBeVisible()
    gate.release()
    await expect(
      page.getByText('团队已切换，文件保留在原团队，未关联当前素材组', {
        exact: true,
      }),
    ).toBeVisible()
    expect(calls.materialAttachRequests()).toEqual([])
    expect(calls.destructiveRequests()).toEqual([])
  } finally {
    gate.release()
  }
})

test('AI upload: AI-only material upload attaches and previews through AI endpoints', async ({
  page,
}) => {
  await installWorkbenchApi(page, { aiOnly: true, imageSize: [450, 800] })
  const uploads: string[] = []
  page.on('request', (request) => {
    if (request.method() === 'POST')
      uploads.push(new URL(request.url()).pathname)
  })
  await page.goto('/#/ai-workbench/assets')
  await page
    .getByLabel('上传素材', { exact: true })
    .setInputFiles({
      name: 'uploaded.png',
      mimeType: 'image/png',
      buffer: Buffer.from(proportionImage([450, 800])),
    })
  const uploaded = page.getByRole('button', {
    name: '查看素材 uploaded.png',
    exact: true,
  })
  await expectCompleteProportions(uploaded.locator('img'), [450, 800])
  await uploaded.click()
  await expectCompleteProportions(
    page.getByRole('region', { name: '素材详情' }).locator('img'),
    [450, 800],
  )
  expect(uploads).toEqual([
    '/api/v1/ai-workbench/assets',
    `/api/v1/ai-workbench/product-material-groups/${materialGroupId}/assets`,
  ])
})

test('AI upload: partial multi-file failure keeps successes and reports HTML 413 without replay', async ({
  page,
}) => {
  await installWorkbenchApi(page, { aiOnly: true, failUploadName: 'bad.png' })
  let posts = 0
  page.on('request', (request) => {
    if (
      request.method() === 'POST' &&
      new URL(request.url()).pathname.endsWith('/ai-workbench/assets')
    )
      posts += 1
  })
  await page.goto('/#/ai-workbench/generate')
  await page.getByLabel('上传商品图片', { exact: true }).setInputFiles([
    {
      name: 'good.png',
      mimeType: 'image/png',
      buffer: Buffer.from(controlledAssetImage),
    },
    {
      name: 'bad.png',
      mimeType: 'image/png',
      buffer: Buffer.from(controlledAssetImage),
    },
  ])
  await expect(
    page.getByLabel('即时生成配置').getByAltText('good.png'),
  ).toBeVisible()
  await expect(page.getByText(/上传 bad.png.*10 MiB.*HTTP_413/)).toBeVisible()
  await page.reload()
  await expect(
    page.getByLabel('即时生成配置').getByAltText('good.png'),
  ).toBeVisible()
  expect(posts).toBe(2)
})

test('AI upload: attach failure and cleanup failure retain distinct request diagnostics', async ({
  page,
}) => {
  const calls = await installWorkbenchApi(page, {
    aiOnly: true,
    failAttach: true,
    failCleanup: true,
  })
  await page.goto('/#/ai-workbench/assets')
  await page
    .getByLabel('上传素材', { exact: true })
    .setInputFiles({
      name: 'uploaded.png',
      mimeType: 'image/png',
      buffer: Buffer.from(controlledAssetImage),
    })
  await expect(
    page.getByText(
      /关联 uploaded.png.*MODULE_ACCESS_DENIED.*attach-request.*清理未完成.*ASSET_STORAGE_UNAVAILABLE.*cleanup-request/,
    ),
  ).toBeVisible()
  expect(calls.destructiveRequests()).toHaveLength(1)
  expect(calls.destructiveRequests()[0]).toContain(
    '/api/v1/ai-workbench/assets/',
  )
})

function proportionImage([width, height]: readonly [number, number]): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
    <path d="M0 0H${width}V${height}H0Z" fill="#dc2626"/>
    <path d="M${width / 2} 0H${width}V${height / 2}H${width / 2}Z" fill="#16a34a"/>
    <path d="M0 ${height / 2}H${width / 2}V${height}H0Z" fill="#2563eb"/>
    <path d="M${width / 2} ${height / 2}H${width}V${height}H${width / 2}Z" fill="#eab308"/>
    <circle cx="${width / 2}" cy="${height / 2}" r="${Math.min(width, height) / 10}" fill="white"/>
  </svg>`
}

async function expectCompleteProportions(
  image: Locator,
  size: readonly [number, number],
): Promise<void> {
  await expect(image).toBeVisible()
  await expect
    .poll(() =>
      image.evaluate((element) => {
        const img = element as HTMLImageElement
        return img.complete && img.naturalWidth > 0
      }),
    )
    .toBe(true)
  await image.page().mouse.move(0, 0)
  // Finish dialog/card transitions before measuring the screenshot coordinate
  // system (a modal can otherwise still be scaled while its image is decoded).
  const png = await image.screenshot({
    animations: 'disabled',
    path: test.info().outputPath(`probe-${size[0]}-${size[1]}.png`),
  })
  const geometry = await image.evaluate((element) => {
    const img = element as HTMLImageElement
    const box = img.getBoundingClientRect()
    return {
      natural: [img.naturalWidth, img.naturalHeight],
      fit: getComputedStyle(img).objectFit,
      position: getComputedStyle(img).objectPosition,
      width: box.width,
      height: box.height,
    }
  })
  expect(geometry.natural).toEqual(size)
  expect(geometry.fit).toBe('contain')
  expect(geometry.position).toBe('50% 50%')
  const scale = Math.min(geometry.width / size[0], geometry.height / size[1])
  const painted = { width: size[0] * scale, height: size[1] * scale }
  expect(painted.width).toBeLessThanOrEqual(geometry.width + 0.01)
  expect(painted.height).toBeLessThanOrEqual(geometry.height + 0.01)

  // The img element can remain square. Sample the actual contained image's four
  // quadrants in a browser-decoded screenshot, not its element aspect ratio.
  const colors = await image.page().evaluate(
    async ({ bytes, box, painted }) => {
      const bitmap = await createImageBitmap(
        new Blob([new Uint8Array(bytes)], { type: 'image/png' }),
      )
      const canvas = document.createElement('canvas')
      canvas.width = bitmap.width
      canvas.height = bitmap.height
      const context = canvas.getContext('2d')!
      context.drawImage(bitmap, 0, 0)
      const ratioX = bitmap.width / box.width
      const ratioY = bitmap.height / box.height
      const colors = [
        [0.2, 0.2],
        [0.8, 0.2],
        [0.2, 0.8],
        [0.8, 0.8],
      ].map(([x, y]) => {
        const px =
          ((box.width - painted.width) / 2 + painted.width * x!) * ratioX
        const py =
          ((box.height - painted.height) / 2 + painted.height * y!) * ratioY
        return [
          ...context.getImageData(Math.floor(px), Math.floor(py), 1, 1).data,
        ].slice(0, 3)
      })
      bitmap.close()
      return colors
    },
    { bytes: [...png], box: geometry, painted },
  )
  const expectedColors = [
    [220, 38, 38],
    [22, 163, 74],
    [37, 99, 235],
    [234, 179, 8],
  ]
  colors.forEach((color, index) =>
    color.forEach((channel, channelIndex) => {
      expect(
        Math.abs(channel - expectedColors[index]![channelIndex]!),
        JSON.stringify({ geometry, colors }),
      ).toBeLessThanOrEqual(20)
    }),
  )
}

for (const [label, size] of [
  ['landscape', [800, 450]],
  ['portrait', [450, 800]],
  ['long', [320, 1600]],
  ['square', [512, 512]],
] as const) {
  test(`image proportions: ${label} inputs, outputs and materials`, async ({
    page,
  }, testInfo) => {
    const calls = await installWorkbenchApi(page, {
      controlledJob: true,
      imageSize: size,
      aiOnly: true,
    })
    await page.goto('/#/ai-workbench/generate')
    await page
      .getByLabel('即时生成配置')
      .getByRole('button', { name: '素材库', exact: true })
      .click()
    const choice = page.getByRole('button', {
      name: '选择素材 商品图.png',
      exact: true,
    })
    await expectCompleteProportions(choice.locator('img'), size)
    await choice.click()
    await page
      .getByRole('dialog')
      .getByRole('button', { name: '选择', exact: true })
      .click()
    await expectCompleteProportions(
      page.getByLabel('即时生成配置').getByAltText('商品图.png'),
      size,
    )
    await page.getByLabel('提示词').fill('受控比例回归，不调用生成平台')
    await page.getByRole('button', { name: '生成', exact: true }).click()
    await expect.poll(calls.submitCount).toBe(1)
    calls.setControlledJobStatus('SUCCESS')
    const result = page.locator('[data-result-status="SUCCESS"]')
    await expectCompleteProportions(result.getByAltText('真实结果.png'), size)
    await result.getByRole('button', { name: /^预览 / }).click()
    const preview = page.getByRole('region', { name: '图片预览' })
    await expectCompleteProportions(preview.locator('img'), size)
    await page.screenshot({ path: testInfo.outputPath(`${label}-preview.png`) })
    await page
      .getByRole('dialog')
      .getByRole('button', { name: '关闭', exact: true })
      .click()

    await page.goto('/#/ai-workbench/assets')
    const card = page.getByRole('button', {
      name: '查看素材 商品图.png',
      exact: true,
    })
    await expectCompleteProportions(card.locator('img'), size)
    await card.click()
    const inspector = page.getByRole('region', { name: '素材详情' })
    await expectCompleteProportions(inspector.locator('img'), size)
    await page.screenshot({
      path: testInfo.outputPath(`${label}-materials.png`),
    })

    expect(calls.archiveRequests()).toEqual([])
    expect(calls.destructiveRequests()).toEqual([])
    expect(calls.assetImageRequests()).toContainEqual({
      assetId: outputAssetId,
      resource: 'content',
    })
  })

  test(`image proportions: ${label} batch outputs and records`, async ({
    page,
  }) => {
    const batchCalls = await installWorkbenchApi(page, {
      controlledJob: true,
      batchScenario: true,
      imageSize: size,
      aiOnly: true,
    })
    await submitControlledBatch(page)
    await expect.poll(batchCalls.submitCount).toBe(1)
    batchCalls.setControlledJobStatus('SUCCESS')
    await expect(page.getByTestId('batch-execution-summary')).toContainText(
      '已完成',
    )
    await expect(page.getByTestId('batch-execution-summary')).toContainText(
      '4 / 4',
    )
    const detail = await selectBatchProduct(page, '手机支架')
    await expandBatchTemplateGroup(page, '电商标准套图')
    await expectCompleteProportions(
      detail.getByAltText('纯白主图 结果 1'),
      size,
    )
    await page
      .getByRole('navigation', { name: 'AI 功能入口' })
      .getByRole('button', { name: '生成记录' })
      .click()
    await page.getByRole('button', { name: '查看', exact: true }).click()
    const tree = page.getByTestId('batch-result-tree')
    await expectCompleteProportions(tree.locator('img').first(), size)
    expect(batchCalls.archiveRequests()).toEqual([])
    expect(batchCalls.destructiveRequests()).toEqual([])
  })
}

for (const [label, size] of [
  ['long', [320, 1600]],
  ['landscape', [1600, 320]],
] as const) {
  test(`image proportions: ${label} preview zoom keeps all edges reachable in a small viewport`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: 800, height: 650 })
    const calls = await installWorkbenchApi(page, { imageSize: size })
    await page.goto('/#/ai-workbench/assets')
    await page
      .getByRole('button', { name: '查看素材 商品图.png', exact: true })
      .click()
    await page
      .getByRole('region', { name: '素材详情' })
      .getByRole('button', { name: '预览', exact: true })
      .click()
    const preview = page.getByRole('region', { name: '图片预览' })
    await expectCompleteProportions(preview.locator('img'), size)
    await page.screenshot({
      path: testInfo.outputPath(`${label}-small-fit.png`),
    })
    for (let index = 0; index < 3; index += 1)
      await page.getByRole('button', { name: '放大预览', exact: true }).click()
    await preview.screenshot({
      path: testInfo.outputPath(`${label}-small-zoom.png`),
      animations: 'disabled',
    })
    const edges = await preview
      .locator('.asset-preview-dialog__canvas')
      .evaluate((canvas) => {
        canvas.scrollTop = 0
        canvas.scrollLeft = 0
        const img = canvas.querySelector('img')!
        const start = img.getBoundingClientRect()
        const viewport = canvas.getBoundingClientRect()
        canvas.scrollTop = canvas.scrollHeight
        canvas.scrollLeft = canvas.scrollWidth
        const end = img.getBoundingClientRect()
        return {
          topReachable: start.top >= viewport.top - 1,
          leftReachable: start.left >= viewport.left - 1,
          bottomReachable: end.bottom <= viewport.bottom + 1,
          rightReachable: end.right <= viewport.right + 1,
          dialogInsideViewport:
            canvas.closest('[role="dialog"]')!.getBoundingClientRect().bottom <=
            window.innerHeight + 1,
        }
      })
    expect(edges).toEqual({
      topReachable: true,
      leftReachable: true,
      bottomReachable: true,
      rightReachable: true,
      dialogInsideViewport: true,
    })
    await page
      .getByRole('button', { name: '查看下一张图片', exact: true })
      .click()
    await expect(preview.locator('.asset-preview-dialog__image')).toHaveCSS(
      'transform',
      'matrix(1, 0, 0, 1, 0, 0)',
    )
    await expectCompleteProportions(preview.locator('img'), size)
    const download = page.waitForEvent('download')
    await page.getByRole('button', { name: /^下载 / }).click()
    expect((await download).suggestedFilename()).toBe('商品图-侧面.png')
    expect(calls.destructiveRequests()).toEqual([])
  })
}

const templateGroup: TemplateGroupReadDto = {
  template_group_id: groupId,
  name: '电商标准套图',
  mode: 'NORMAL_GENERATION',
  enabled: true,
  created_at: timestamp,
  updated_at: timestamp,
  prompt_templates: [
    {
      prompt_template_id: templateId,
      template_group_id: groupId,
      name: '纯白主图',
      enabled: true,
      output_role: 'MAIN_IMAGE',
      output_format: 'SINGLE',
      size: '1:1',
      count: 1,
      variables: [],
      prompt: '一件商品放在干净的白色背景上',
      sort_order: 0,
      created_at: timestamp,
      updated_at: timestamp,
    },
  ],
}

const detailTemplateGroup: TemplateGroupReadDto = {
  template_group_id: detailGroupId,
  name: '场景详情套图',
  mode: 'NORMAL_GENERATION',
  enabled: true,
  created_at: timestamp,
  updated_at: timestamp,
  prompt_templates: [
    {
      prompt_template_id: detailTemplateId,
      template_group_id: detailGroupId,
      name: '细节展示',
      enabled: true,
      output_role: 'DETAIL_IMAGE',
      output_format: 'SINGLE',
      size: '3:4',
      count: 1,
      variables: [],
      prompt: '展示商品材质与关键细节',
      sort_order: 0,
      created_at: timestamp,
      updated_at: timestamp,
    },
  ],
}

const materialGroup: ProductMaterialGroupReadDto = {
  material_group_id: materialGroupId,
  name: '手机支架',
  enabled: true,
  normal_generation_enabled: true,
  style_replication_enabled: false,
  created_at: timestamp,
  updated_at: timestamp,
  assets: [
    {
      role: 'PRODUCT_SOURCE',
      created_at: timestamp,
      asset: {
        asset_id: inputAssetId,
        media_type: 'image',
        original_filename: '商品图.png',
        content_type: 'image/png',
        size_bytes: 128,
        sha256: 'a'.repeat(64),
        source_type: 'upload',
        created_at: timestamp,
      },
    },
    {
      role: 'PRODUCT_SOURCE',
      created_at: timestamp,
      asset: {
        asset_id: supplementalInputAssetId,
        media_type: 'image',
        original_filename: '商品图-侧面.png',
        content_type: 'image/png',
        size_bytes: 144,
        sha256: 'b'.repeat(64),
        source_type: 'upload',
        created_at: timestamp,
      },
    },
    ...generatedProductAssetIds.map((assetId, index) => ({
      role: 'AI_OUTPUT' as const,
      created_at: timestamp,
      asset: {
        asset_id: assetId,
        media_type: 'image' as const,
        original_filename:
          index === 0 ? '历史AI成品.png' : `历史AI成品-${index + 1}.png`,
        content_type: 'image/png',
        size_bytes: 256 + index,
        sha256: generatedProductAssetHashes[index]!.repeat(64),
        source_type: 'ai_generated' as const,
        created_at: timestamp,
      },
    })),
  ],
  template_bindings: [
    {
      material_group_id: materialGroupId,
      template_group_id: groupId,
      generation_mode: 'NORMAL_GENERATION',
      position: 0,
      created_at: timestamp,
    },
    {
      material_group_id: materialGroupId,
      template_group_id: detailGroupId,
      generation_mode: 'NORMAL_GENERATION',
      position: 1,
      created_at: timestamp,
    },
  ],
}

const secondMaterialGroup: ProductMaterialGroupReadDto = {
  material_group_id: secondMaterialGroupId,
  name: '马克杯',
  enabled: true,
  normal_generation_enabled: true,
  style_replication_enabled: false,
  created_at: timestamp,
  updated_at: timestamp,
  assets: [
    {
      role: 'PRODUCT_SOURCE',
      created_at: timestamp,
      asset: {
        asset_id: secondInputAssetId,
        media_type: 'image',
        original_filename: '马克杯商品图.png',
        content_type: 'image/png',
        size_bytes: 144,
        sha256: 'c'.repeat(64),
        source_type: 'upload',
        created_at: timestamp,
      },
    },
  ],
  template_bindings: [
    {
      material_group_id: secondMaterialGroupId,
      template_group_id: groupId,
      generation_mode: 'NORMAL_GENERATION',
      position: 0,
      created_at: timestamp,
    },
    {
      material_group_id: secondMaterialGroupId,
      template_group_id: detailGroupId,
      generation_mode: 'NORMAL_GENERATION',
      position: 1,
      created_at: timestamp,
    },
  ],
}

function generationItem(
  status: GenerationItemReadDto['status'],
  attemptCount = 1,
  archived = false,
): GenerationItemReadDto {
  const successful = status === 'SUCCESS'
  const failed = status === 'FAILED'
  return {
    generation_item_id: itemId,
    position: 0,
    status,
    final_prompt: '一件商品放在干净的白色背景上',
    output_role: 'MAIN_IMAGE',
    output_format: 'SINGLE',
    size: '1:1',
    source_product_position: null,
    source_template_group_position: null,
    source_prompt_template_position: null,
    output_ordinal: 0,
    source_product_material_group_id: null,
    source_template_group_id: null,
    source_prompt_template_id: null,
    product_name_snapshot: null,
    template_group_name_snapshot: null,
    prompt_template_name_snapshot: null,
    attempt_count: attemptCount,
    last_failure_code: failed ? 'PROVIDER_FAILED' : null,
    last_failure_message: failed ? '生成服务暂时不可用' : null,
    last_failed_at: failed ? timestamp : null,
    started_at: status === 'PENDING' ? null : timestamp,
    finished_at: successful || failed ? timestamp : null,
    archived_material_group_id: archived ? materialGroupId : null,
    archived_material_group_name_snapshot: archived ? materialGroup.name : null,
    archived_at: archived ? timestamp : null,
    input_assets: [
      {
        input_role: 'PRODUCT_SOURCE',
        position: 0,
        asset: materialGroup.assets[0]!.asset,
      },
    ],
    output_asset: successful
      ? {
          asset_id: outputAssetId,
          media_type: 'image',
          original_filename: '真实结果.png',
          content_type: 'image/png',
          size_bytes: 256,
          sha256: 'b'.repeat(64),
          source_type: 'ai_generated',
          created_at: timestamp,
        }
      : null,
  }
}

function generationJob(
  status: GenerationJobReadDto['status'],
  itemStatus: GenerationItemReadDto['status'],
  attemptCount = 1,
  archived = false,
): GenerationJobReadDto {
  const item = generationItem(itemStatus, attemptCount, archived)
  return {
    generation_job_id: jobId,
    submission_key: 'real-api-e2e',
    model_id: modelId,
    model_code: 'gpt-image-2',
    model_display_name: 'GPT Image 2',
    work_mode: 'INSTANT',
    mode: 'NORMAL_GENERATION',
    compress_output_under_1000kb: false,
    status,
    input_summary: { count: 1, primary_name: '商品图.png' },
    created_by_display_name: '开发管理员',
    created_at: timestamp,
    updated_at: timestamp,
    started_at: status === 'PENDING' ? null : timestamp,
    finished_at:
      status === 'SUCCESS' || status === 'PARTIAL_FAILED' || status === 'FAILED'
        ? timestamp
        : null,
    total_count: 1,
    pending_count: itemStatus === 'PENDING' ? 1 : 0,
    running_count: itemStatus === 'RUNNING' ? 1 : 0,
    success_count: itemStatus === 'SUCCESS' ? 1 : 0,
    failed_count: itemStatus === 'FAILED' ? 1 : 0,
    items: [item],
  }
}

const batchItemFixtures = [
  {
    itemId: '77777777-7777-4777-8777-777777777771',
    outputAssetId: '88888888-8888-4888-8888-888888888881',
    outputFilename: '手机支架-主图.png',
    productId: materialGroupId,
    productName: materialGroup.name,
    inputAsset: materialGroup.assets[0]!.asset,
    productPosition: 0,
    templateGroupId: groupId,
    templateGroupName: templateGroup.name,
    templateGroupPosition: 0,
    templateId,
    templateName: '纯白主图',
    outputRole: 'MAIN_IMAGE' as const,
    size: '1:1' as const,
  },
  {
    itemId: '77777777-7777-4777-8777-777777777772',
    outputAssetId: '88888888-8888-4888-8888-888888888882',
    outputFilename: '手机支架-详情.png',
    productId: materialGroupId,
    productName: materialGroup.name,
    inputAsset: materialGroup.assets[0]!.asset,
    productPosition: 0,
    templateGroupId: detailGroupId,
    templateGroupName: detailTemplateGroup.name,
    templateGroupPosition: 1,
    templateId: detailTemplateId,
    templateName: '细节展示',
    outputRole: 'DETAIL_IMAGE' as const,
    size: '3:4' as const,
  },
  {
    itemId: '77777777-7777-4777-8777-777777777773',
    outputAssetId: '88888888-8888-4888-8888-888888888883',
    outputFilename: '马克杯-主图.png',
    productId: secondMaterialGroupId,
    productName: secondMaterialGroup.name,
    inputAsset: secondMaterialGroup.assets[0]!.asset,
    productPosition: 1,
    templateGroupId: groupId,
    templateGroupName: templateGroup.name,
    templateGroupPosition: 0,
    templateId,
    templateName: '纯白主图',
    outputRole: 'MAIN_IMAGE' as const,
    size: '1:1' as const,
  },
  {
    itemId: '77777777-7777-4777-8777-777777777774',
    outputAssetId: '88888888-8888-4888-8888-888888888884',
    outputFilename: '马克杯-详情.png',
    productId: secondMaterialGroupId,
    productName: secondMaterialGroup.name,
    inputAsset: secondMaterialGroup.assets[0]!.asset,
    productPosition: 1,
    templateGroupId: detailGroupId,
    templateGroupName: detailTemplateGroup.name,
    templateGroupPosition: 1,
    templateId: detailTemplateId,
    templateName: '细节展示',
    outputRole: 'DETAIL_IMAGE' as const,
    size: '3:4' as const,
  },
] as const

function batchGenerationItem(
  fixture: (typeof batchItemFixtures)[number],
  position: number,
  status: GenerationItemReadDto['status'],
): GenerationItemReadDto {
  const successful = status === 'SUCCESS'
  const failed = status === 'FAILED'
  return {
    generation_item_id: fixture.itemId,
    position,
    status,
    final_prompt:
      fixture.outputRole === 'MAIN_IMAGE'
        ? '一件商品放在干净的白色背景上'
        : '展示商品材质与关键细节',
    output_role: fixture.outputRole,
    output_format: 'SINGLE',
    size: fixture.size,
    source_product_position: fixture.productPosition,
    source_template_group_position: fixture.templateGroupPosition,
    source_prompt_template_position: 0,
    output_ordinal: 0,
    source_product_material_group_id: fixture.productId,
    source_template_group_id: fixture.templateGroupId,
    source_prompt_template_id: fixture.templateId,
    product_name_snapshot: fixture.productName,
    template_group_name_snapshot: fixture.templateGroupName,
    prompt_template_name_snapshot: fixture.templateName,
    attempt_count: 1,
    last_failure_code: failed ? 'PROVIDER_FAILED' : null,
    last_failure_message: failed ? '生成服务暂时不可用' : null,
    last_failed_at: failed ? timestamp : null,
    started_at: status === 'PENDING' ? null : timestamp,
    finished_at: successful || failed ? timestamp : null,
    archived_material_group_id: successful ? fixture.productId : null,
    archived_material_group_name_snapshot: successful
      ? fixture.productName
      : null,
    archived_at: successful ? timestamp : null,
    input_assets: [
      {
        input_role: 'PRODUCT_SOURCE',
        position: 0,
        asset: fixture.inputAsset,
      },
    ],
    output_asset: successful
      ? {
          asset_id: fixture.outputAssetId,
          media_type: 'image',
          original_filename: fixture.outputFilename,
          content_type: 'image/png',
          size_bytes: 256 + position,
          sha256: String(position + 1).repeat(64),
          source_type: 'ai_generated',
          created_at: timestamp,
        }
      : null,
  }
}

function batchGenerationJob(status: ControlledJobStatus): GenerationJobReadDto {
  const itemStatuses: GenerationItemReadDto['status'][] =
    status === 'SUCCESS'
      ? ['SUCCESS', 'SUCCESS', 'SUCCESS', 'SUCCESS']
      : status === 'PARTIAL_FAILED'
        ? ['SUCCESS', 'FAILED', 'SUCCESS', 'FAILED']
        : status === 'RUNNING'
          ? ['SUCCESS', 'RUNNING', 'PENDING', 'PENDING']
          : ['PENDING', 'PENDING', 'PENDING', 'PENDING']
  const items = batchItemFixtures.map((fixture, index) =>
    batchGenerationItem(fixture, index, itemStatuses[index]!),
  )
  const count = (itemStatus: GenerationItemReadDto['status']) =>
    items.filter((item) => item.status === itemStatus).length
  return {
    generation_job_id: jobId,
    submission_key: 'batch-real-api-e2e',
    model_id: modelId,
    model_code: 'gpt-image-2',
    model_display_name: 'GPT Image 2',
    work_mode: 'BATCH',
    mode: 'NORMAL_GENERATION',
    compress_output_under_1000kb: false,
    status,
    input_summary: { count: 2, primary_name: '2 个产品' },
    created_by_display_name: '开发管理员',
    created_at: timestamp,
    updated_at: timestamp,
    started_at: status === 'PENDING' ? null : timestamp,
    finished_at:
      status === 'SUCCESS' || status === 'PARTIAL_FAILED' ? timestamp : null,
    total_count: items.length,
    pending_count: count('PENDING'),
    running_count: count('RUNNING'),
    success_count: count('SUCCESS'),
    failed_count: count('FAILED'),
    items,
  }
}

async function installWorkbenchApi(
  page: Page,
  options: WorkbenchApiOptions = {},
) {
  let phase: 'initial' | 'retry' | 'success' = 'initial'
  let controlledJobStatus: ControlledJobStatus = 'PENDING'
  let pollCount = 0
  let submitCount = 0
  let jobDetailCount = 0
  let heldJobDetailCount = 0
  let expireNextRequest = false
  let failJobDetail = false
  let nextJobDetailGate: Promise<void> | null = null
  let submittedBody: Record<string, unknown> | null = null
  const submittedBodies: Record<string, unknown>[] = []
  let retryBody: Record<string, unknown> | null = null
  const archiveRequests: string[] = []
  const materialAttachRequests: string[] = []
  const assetContentRequests: string[] = []
  const assetImageRequests: Array<{
    assetId: string
    resource: 'content' | 'thumbnail'
  }> = []
  const destructiveRequests: string[] = []
  let assetContentGateUsed = false
  let assetContentFailuresRemaining = options.failAssetContentRequests ?? 0
  let authenticated = true
  let loginName = 'administrator-preview'

  const currentUser = () => ({
    user_id: '00000000-0000-4000-8000-000000000001',
    display_name: loginName.includes('multi')
      ? '多团队测试人员'
      : loginName.includes('administrator')
        ? '管理员预览'
        : '测试人员',
  })
  const currentTeams = () => [
    {
      membership_id: options.superAccount
        ? null
        : '00000000-0000-4000-8000-000000000011',
      team_id: defaultTeamId,
      team_name: '默认团队',
      team_enabled: true,
      role_code: options.superAccount ? 'super_account' : 'member',
      data_scope: options.superAccount ? 'all' : 'team',
      membership_enabled: true,
    },
    ...((loginName.includes('multi') || options.superAccount) &&
    !options.singleTeam
      ? [
          {
            membership_id: options.superAccount
              ? null
              : '00000000-0000-4000-8000-000000000012',
            team_id: shopeeTeamId,
            team_name: options.superAccount ? 'shopee' : '运营团队',
            team_enabled: true,
            role_code: options.superAccount ? 'super_account' : 'member',
            data_scope: options.superAccount ? 'all' : 'team',
            membership_enabled: true,
          },
        ]
      : []),
  ]
  const requireAuthenticated = async (
    route: Parameters<Page['route']>[1],
    data: unknown,
  ) => {
    if (!authenticated) {
      await route.fulfill({
        status: 401,
        json: {
          code: 'HUMAN_SESSION_INVALID',
          message: '登录会话已失效，请重新登录',
        },
      })
      return false
    }
    await route.fulfill({ json: data })
    return true
  }

  await page.route('**/api/v1/auth/me', async (route) => {
    await requireAuthenticated(route, currentUser())
  })
  await page.route('**/api/v1/access/me/teams', async (route) => {
    await requireAuthenticated(route, currentTeams())
  })
  await page.route(
    '**/api/v1/access-management/me/module-access',
    async (route) => {
      await requireAuthenticated(route, {
        module_codes: options.aiOnly
          ? ['ai-workbench']
          : [
              'shop',
              'asset',
              'ai-workbench',
              'device',
              'task',
              'schedule',
              'settings',
            ],
        is_access_administrator: !options.aiOnly,
        is_super_account: options.superAccount === true,
      })
    },
  )
  await page.route('**/api/v1/auth/login', async (route) => {
    const body = route.request().postDataJSON() as {
      login_name?: unknown
    }
    loginName =
      typeof body.login_name === 'string' && body.login_name.trim()
        ? body.login_name.trim().toLowerCase()
        : 'operator'
    authenticated = true
    await route.fulfill({ json: currentUser() })
  })
  await page.route('**/api/v1/auth/logout', async (route) => {
    authenticated = false
    await route.fulfill({ status: 204 })
  })

  page.on('request', (request) => {
    const path = new URL(request.url()).pathname
    if (request.method() === 'DELETE') {
      destructiveRequests.push(request.url())
    }
    if (path.endsWith('/archive')) archiveRequests.push(path)
    if (
      /\/product-material-groups\/[^/]+\/assets$/.test(path) &&
      request.method() === 'POST'
    )
      materialAttachRequests.push(path)
  })

  const fulfillAssetImage = async (route: Parameters<Page['route']>[1]) => {
    const segments = new URL(route.request().url()).pathname.split('/')
    const assetId = segments.at(-2) ?? ''
    const resource = segments.at(-1)
    assetContentRequests.push(assetId)
    if (resource === 'content' || resource === 'thumbnail') {
      assetImageRequests.push({ assetId, resource })
    }
    if (
      resource === 'content' &&
      options.assetContentGate &&
      !assetContentGateUsed
    ) {
      assetContentGateUsed = true
      await options.assetContentGate
    }
    if (resource === 'content' && assetContentFailuresRemaining > 0) {
      assetContentFailuresRemaining -= 1
      await route.fulfill({
        status: 503,
        json: {
          code: 'ASSET_CONTENT_UNAVAILABLE',
          message: '原图暂时无法读取',
        },
      })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'image/svg+xml',
      body: Buffer.from(
        options.imageSize
          ? proportionImage(options.imageSize)
          : controlledAssetImage,
      ),
    })
  }
  await page.route('**/api/v1/assets**', async (route) => {
    throw new Error(
      `AI must not fall back to general Asset API: ${route.request().method()}`,
    )
  })

  const uploads: Array<(typeof materialGroup.assets)[number]> = []
  const attachedUploadGroups = new Map<string, string>()
  await page.route('**/api/v1/ai-workbench/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (
      /^\/api\/v1\/ai-workbench\/assets\/[^/]+\/(content|thumbnail)$/.test(path)
    ) {
      await fulfillAssetImage(route)
      return
    }
    if (path === '/api/v1/ai-workbench/assets' && method === 'POST') {
      const filename =
        /filename="([^"]+)"/.exec(request.postData() ?? '')?.[1] ??
        'uploaded.png'
      if (filename === options.failUploadName) {
        await route.fulfill({
          status: 413,
          contentType: 'text/html',
          body: '<html>413 Request Entity Too Large</html>',
        })
        return
      }
      const original = materialGroup.assets[0]!
      const uploaded = {
        ...original,
        asset: {
          ...original.asset,
          asset_id: `99999999-9999-4999-8999-${String(uploads.length + 1).padStart(12, '0')}`,
          original_filename: filename,
        },
      }
      uploads.push(uploaded)
      if (options.uploadGate) await options.uploadGate
      await route.fulfill({ status: 201, json: uploaded.asset })
      return
    }
    if (
      /^\/api\/v1\/ai-workbench\/assets\/[^/]+$/.test(path) &&
      method === 'DELETE'
    ) {
      await route.fulfill(
        options.failCleanup
          ? {
              status: 503,
              json: {
                code: 'ASSET_STORAGE_UNAVAILABLE',
                message: '资产存储挂载不可用',
                request_id: 'cleanup-request',
              },
            }
          : { status: 204 },
      )
      return
    }
    if (
      [materialGroupId, secondMaterialGroupId].some(
        (id) =>
          path === `/api/v1/ai-workbench/product-material-groups/${id}/assets`,
      ) &&
      method === 'POST'
    ) {
      const targetGroup = path.includes(secondMaterialGroupId)
        ? secondMaterialGroup
        : materialGroup
      if (!options.failAttach) {
        attachedUploadGroups.set(
          (request.postDataJSON() as { asset_id: string }).asset_id,
          targetGroup.material_group_id,
        )
      }
      await route.fulfill(
        options.failAttach
          ? {
              status: 403,
              json: {
                code: 'MODULE_ACCESS_DENIED',
                message: '没有模块权限',
                request_id: 'attach-request',
              },
            }
          : {
              json: {
                ...targetGroup,
                assets: [...targetGroup.assets, ...uploads],
              },
            },
      )
      return
    }

    if (expireNextRequest) {
      expireNextRequest = false
      await route.fulfill({
        status: 401,
        json: {
          code: 'HUMAN_SESSION_INVALID',
          message: '登录会话已失效，请重新登录',
        },
      })
      return
    }

    if (path.endsWith('/models')) {
      await route.fulfill({
        json: [
          {
            model_id: modelId,
            model_code: 'gpt-image-2',
            display_name: 'GPT Image 2',
            capabilities: ['NORMAL_GENERATION', 'STYLE_REPLICATION'],
            max_input_images: 6,
            supported_sizes: ['1:1', '3:4', '4:3', '16:9'],
            supported_resolutions: ['1k'],
            is_default: true,
          },
          {
            model_id: alternateModelId,
            model_code: 'gpt-image-2-alternate',
            display_name: 'GPT Image 2 Backup',
            capabilities: ['NORMAL_GENERATION', 'STYLE_REPLICATION'],
            max_input_images: 6,
            supported_sizes: ['1:1', '3:4', '4:3', '16:9'],
            supported_resolutions: ['1k'],
            is_default: false,
          },
        ],
      })
      return
    }
    if (path.endsWith('/template-groups') && method === 'GET') {
      const groups = options.batchScenario
        ? [templateGroup, detailTemplateGroup]
        : [templateGroup]
      await route.fulfill({
        json: {
          items: groups.map((group) => ({
            template_group_id: group.template_group_id,
            name: group.name,
            mode: group.mode,
            enabled: true,
            created_at: timestamp,
            updated_at: timestamp,
          })),
          total: groups.length,
          page: 1,
          page_size: Number(url.searchParams.get('page_size') ?? 20),
        },
      })
      return
    }
    if (path.endsWith(`/template-groups/${groupId}`) && method === 'GET') {
      await route.fulfill({ json: templateGroup })
      return
    }
    if (
      path.endsWith(`/template-groups/${detailGroupId}`) &&
      method === 'GET'
    ) {
      await route.fulfill({ json: detailTemplateGroup })
      return
    }
    if (path.endsWith('/product-material-groups') && method === 'GET') {
      let groups =
        options.batchScenario || options.superAccount
          ? [materialGroup, secondMaterialGroup]
          : [materialGroup]
      if (options.superAccount) {
        const team = request.headers()['x-team-id']
        if (team)
          groups = [team === shopeeTeamId ? secondMaterialGroup : materialGroup]
      }
      await route.fulfill({
        json: {
          items: groups.map((group) => ({
            material_group_id: group.material_group_id,
            name: group.name,
            enabled: true,
            normal_generation_enabled: true,
            style_replication_enabled: false,
            created_at: timestamp,
            updated_at: timestamp,
          })),
          total: groups.length,
          page: 1,
          page_size: Number(url.searchParams.get('page_size') ?? 20),
        },
      })
      return
    }
    if (
      path.endsWith(`/product-material-groups/${materialGroupId}`) &&
      method === 'GET'
    ) {
      await route.fulfill({
        json: {
          ...materialGroup,
          assets: [
            ...materialGroup.assets,
            ...uploads.filter(
              (link) =>
                attachedUploadGroups.get(link.asset.asset_id) ===
                materialGroupId,
            ),
          ],
        },
      })
      return
    }
    if (
      path.endsWith(`/product-material-groups/${secondMaterialGroupId}`) &&
      method === 'GET'
    ) {
      await route.fulfill({
        json: {
          ...secondMaterialGroup,
          assets: [
            ...secondMaterialGroup.assets,
            ...uploads.filter(
              (link) =>
                attachedUploadGroups.get(link.asset.asset_id) ===
                secondMaterialGroupId,
            ),
          ],
        },
      })
      return
    }
    if (path.endsWith('/generation-jobs') && method === 'POST') {
      submitCount += 1
      submittedBody = request.postDataJSON() as Record<string, unknown>
      submittedBodies.push(submittedBody)
      pollCount = 0
      if (options.submissionGate) await options.submissionGate
      await route.fulfill({
        status: 202,
        json: options.batchScenario
          ? batchGenerationJob('PENDING')
          : generationJob('PENDING', 'PENDING'),
      })
      return
    }
    if (path.endsWith('/generation-jobs') && method === 'GET') {
      const completed = options.batchScenario
        ? batchGenerationJob(
            controlledJobStatus === 'PARTIAL_FAILED'
              ? 'PARTIAL_FAILED'
              : 'SUCCESS',
          )
        : generationJob('SUCCESS', 'SUCCESS', 2, true)
      await route.fulfill({
        json: {
          items: [completed],
          total: 1,
          page: 1,
          page_size: 20,
        },
      })
      return
    }
    if (path.endsWith(`/generation-jobs/${jobId}`) && method === 'GET') {
      jobDetailCount += 1
      const detailGate = nextJobDetailGate
      nextJobDetailGate = null
      if (detailGate) {
        heldJobDetailCount += 1
        await detailGate
      }
      if (failJobDetail) {
        await route.fulfill({
          status: 503,
          json: {
            code: 'GENERATION_JOB_READ_UNAVAILABLE',
            message: '生成任务暂时无法读取',
          },
        })
        return
      }
      if (options.controlledJob) {
        if (options.batchScenario) {
          await route.fulfill({ json: batchGenerationJob(controlledJobStatus) })
          return
        }
        const itemStatus =
          controlledJobStatus === 'SUCCESS'
            ? 'SUCCESS'
            : controlledJobStatus === 'RUNNING'
              ? 'RUNNING'
              : 'PENDING'
        await route.fulfill({
          json: generationJob(controlledJobStatus, itemStatus),
        })
        return
      }
      if (phase === 'success') {
        await route.fulfill({
          json: generationJob('SUCCESS', 'SUCCESS', 2, true),
        })
        return
      }
      pollCount += 1
      const response =
        pollCount === 1
          ? generationJob('RUNNING', 'RUNNING', phase === 'retry' ? 2 : 1)
          : phase === 'retry'
            ? generationJob('SUCCESS', 'SUCCESS', 2)
            : generationJob('FAILED', 'FAILED')
      if (pollCount > 1 && phase === 'retry') phase = 'success'
      await route.fulfill({ json: response })
      return
    }
    if (path.endsWith('/retry-failed-items') && method === 'POST') {
      retryBody = request.postDataJSON() as Record<string, unknown>
      phase = 'retry'
      pollCount = 0
      await route.fulfill({
        status: 202,
        json: generationJob('PENDING', 'PENDING', 2),
      })
      return
    }
    await route.fulfill({
      status: 500,
      json: { code: 'UNHANDLED_TEST_ROUTE', message: `${method} ${path}` },
    })
  })

  return {
    uploadCount: () => uploads.length,
    materialAttachRequests: () => [...materialAttachRequests],
    submitCount: () => submitCount,
    submittedBody: () => submittedBody,
    submittedBodies: () => [...submittedBodies],
    jobDetailCount: () => jobDetailCount,
    heldJobDetailCount: () => heldJobDetailCount,
    retryBody: () => retryBody,
    archiveRequests: () => [...archiveRequests],
    assetContentRequests: () => [...assetContentRequests],
    assetImageRequests: () => [...assetImageRequests],
    destructiveRequests: () => [...destructiveRequests],
    setControlledJobStatus: (status: ControlledJobStatus) => {
      controlledJobStatus = status
    },
    failControlledJobDetail: (value: boolean) => {
      failJobDetail = value
    },
    holdNextJobDetail: (gate: Promise<void>) => {
      nextJobDetailGate = gate
    },
    expireSessionOnNextRequest: () => {
      expireNextRequest = true
    },
  }
}

function releaseGate(): { promise: Promise<void>; release: () => void } {
  let release!: () => void
  const promise = new Promise<void>((resolve) => {
    release = resolve
  })
  return { promise, release }
}

async function selectInstantSource(page: Page): Promise<void> {
  await page
    .getByLabel('即时生成配置')
    .getByRole('button', { name: '素材库', exact: true })
    .click()
  await page.getByRole('button', { name: '选择素材 商品图.png' }).click()
  await page
    .getByRole('dialog')
    .getByRole('button', { name: '选择', exact: true })
    .click()
}

async function submitControlledBatch(page: Page): Promise<void> {
  await page.goto('/#/ai-workbench/generate')
  await page.getByRole('button', { name: '批量生成', exact: true }).click()
  await expect(page.getByLabel('批量生成模型')).toBeVisible()
  const productList = page.getByTestId('batch-product-list')
  await expect(productList).toContainText('手机支架')
  await expect(productList).toContainText('商品原图 2')
  await expect(productList).toContainText('马克杯')
  await page.getByRole('button', { name: '执行检查', exact: true }).click()
  const preflight = page.getByTestId('batch-preflight')
  await expect(preflight).toBeVisible()
  await expect(preflight.locator('dd')).toHaveText(['2', '2', '0', '4', '4'])
  await page.getByRole('button', { name: '开始生成', exact: true }).click()
}

async function selectBatchProduct(page: Page, productName: string) {
  await page
    .getByRole('button', {
      name: `查看产品任务 ${productName}`,
      exact: true,
    })
    .click()
  const detail = page.getByTestId('batch-product-result-detail')
  await expect(detail).toContainText(productName)
  await expect(
    detail.getByText(templateGroup.name, { exact: true }),
  ).toBeVisible()
  await expect(
    detail.getByText(detailTemplateGroup.name, { exact: true }),
  ).toBeVisible()
  return detail
}

async function expandBatchTemplateGroup(
  page: Page,
  templateGroupName: string,
): Promise<void> {
  const detail = page.getByTestId('batch-product-result-detail')
  const group = detail
    .getByTestId('batch-template-group')
    .filter({ hasText: templateGroupName })
  const content = group.locator('.n-collapse-item__content-wrapper')
  if (!(await content.isVisible())) {
    await group.getByText(templateGroupName, { exact: true }).click()
  }
  await expect(content).toBeVisible()
}

async function readManagementToolbarLayout(
  page: Page,
  options: {
    label: string
    searchLabel: string
    secondaryControlSelector: string
    primaryActionText: string
  },
) {
  const toolbar = page.getByRole('region', { name: options.label })
  await expect(toolbar).toBeVisible()

  return toolbar.evaluate((element, selectors) => {
    const leading = element.querySelector<HTMLElement>(
      '.table-toolbar__leading',
    )
    const actions = element.querySelector<HTMLElement>(
      '.table-toolbar__actions',
    )
    const search = element.querySelector<HTMLElement>(
      `[aria-label="${selectors.searchLabel}"]`,
    )
    const secondary = element.querySelector<HTMLElement>(
      selectors.secondaryControlSelector,
    )
    const primary = Array.from(
      element.querySelectorAll<HTMLButtonElement>('button'),
    ).find((button) =>
      button.textContent?.trim().includes(selectors.primaryActionText),
    )

    if (!leading || !actions || !search || !secondary || !primary) {
      throw new Error('管理工具栏控件未完整渲染')
    }

    const rect = (node: HTMLElement) => {
      const bounds = node.getBoundingClientRect()
      return {
        top: bounds.top,
        height: bounds.height,
        centerY: bounds.top + bounds.height / 2,
      }
    }
    const bounds = element.getBoundingClientRect()

    return {
      toolbar: {
        height: bounds.height,
        overflows: element.scrollWidth > element.clientWidth,
      },
      leading: rect(leading),
      actions: rect(actions),
      search: rect(search),
      secondary: rect(secondary),
      primary: rect(primary),
      pageOverflows:
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth,
    }
  }, options)
}

function expectCompactToolbar(
  layout: Awaited<ReturnType<typeof readManagementToolbarLayout>>,
): void {
  expect(layout.toolbar.overflows).toBe(false)
  expect(layout.pageOverflows).toBe(false)
  expect(Math.abs(layout.leading.top - layout.actions.top)).toBeLessThanOrEqual(
    1,
  )
  expect(
    Math.abs(layout.search.centerY - layout.secondary.centerY),
  ).toBeLessThanOrEqual(1)
  expect(
    Math.abs(layout.search.centerY - layout.primary.centerY),
  ).toBeLessThanOrEqual(1)
  expect(layout.toolbar.height).toBeLessThanOrEqual(layout.search.height + 32)
}

test('keeps real material and template toolbars compact, aligned and responsive', async ({
  page,
}) => {
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))
  await installWorkbenchApi(page)

  const assetToolbar = {
    label: '素材库工具栏',
    searchLabel: '搜索素材',
    secondaryControlSelector: '[aria-label^="筛选："]',
    primaryActionText: '上传素材',
  }

  for (const viewport of [
    { width: 1366, height: 768 },
    { width: 1920, height: 1080 },
  ]) {
    await page.setViewportSize(viewport)
    await page.goto('/#/ai-workbench/assets')
    expectCompactToolbar(await readManagementToolbarLayout(page, assetToolbar))
  }

  await page.getByRole('button', { name: '切换主题' }).click()
  await page
    .locator('.n-dropdown')
    .getByText('石墨浅色', { exact: true })
    .click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  expectCompactToolbar(await readManagementToolbarLayout(page, assetToolbar))
  await page.getByRole('button', { name: '切换主题' }).click()
  await page.locator('.n-dropdown').getByText('午夜青', { exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  expectCompactToolbar(await readManagementToolbarLayout(page, assetToolbar))

  await page.setViewportSize({ width: 760, height: 768 })
  const narrowAssetToolbar = await readManagementToolbarLayout(
    page,
    assetToolbar,
  )
  expect(narrowAssetToolbar.toolbar.overflows).toBe(false)
  expect(narrowAssetToolbar.actions.top).toBeGreaterThan(
    narrowAssetToolbar.leading.top,
  )
  expect(
    Math.abs(
      narrowAssetToolbar.secondary.centerY - narrowAssetToolbar.primary.centerY,
    ),
  ).toBeLessThanOrEqual(1)

  await page.setViewportSize({ width: 1366, height: 768 })
  await page.goto('/#/ai-workbench/templates')
  expectCompactToolbar(
    await readManagementToolbarLayout(page, {
      label: '模板库工具栏',
      searchLabel: '搜索模板',
      secondaryControlSelector: '[aria-label="生成模式"]',
      primaryActionText: '新建模板组',
    }),
  )

  expect(runtimeErrors).toEqual([])
})

test('runs the production workbench through submit, polling, retry, result and records without archive requests', async ({
  page,
}) => {
  test.setTimeout(45_000)
  const calls = await installWorkbenchApi(page)
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))

  await page.goto('/#/ai-workbench/generate')
  await expect(page.getByLabel('生成模型')).toContainText('GPT Image 2')
  await expect(page.getByText('最多 6 张输入图')).toBeVisible()

  await page
    .getByLabel('即时生成配置')
    .getByRole('button', { name: '素材库', exact: true })
    .click()
  await page.getByRole('button', { name: '选择素材 商品图.png' }).click()
  await page
    .getByRole('dialog')
    .getByRole('button', { name: '选择', exact: true })
    .click()
  await page.getByLabel('提示词').fill('一件商品放在干净的白色背景上')
  await page.getByRole('button', { name: '生成', exact: true }).click()

  await expect.poll(calls.submittedBody).toMatchObject({
    work_mode: 'INSTANT',
    model_id: modelId,
    mode: 'NORMAL_GENERATION',
    product_asset_ids: [inputAssetId],
    size: '1:1',
  })
  await expect(page.locator('[data-result-status="FAILED"]')).toBeVisible({
    timeout: 10_000,
  })

  await page.getByRole('button', { name: /重试 生成结果/ }).click()
  await expect.poll(calls.retryBody).toEqual({
    items: [{ item_id: itemId, expected_attempt_count: 1 }],
  })
  const successCard = page.locator('[data-result-status="SUCCESS"]')
  await expect(successCard).toBeVisible({ timeout: 10_000 })
  await expect(successCard.getByAltText('真实结果.png')).toBeVisible()

  await expect(
    successCard.getByRole('button', { name: /更多操作/ }),
  ).toHaveCount(0)
  await expect(page.getByText('保存到素材库', { exact: true })).toHaveCount(0)
  await expect(successCard).not.toContainText('素材库')

  await page
    .getByRole('navigation', { name: 'AI 功能入口' })
    .getByRole('button', { name: '生成记录' })
    .click()
  await expect(page.getByLabel('生成记录列表')).toContainText('GPT Image 2')
  await expect(page.getByLabel('搜索生成记录')).toHaveCount(0)
  await page.getByRole('button', { name: '查看' }).click()
  const drawer = page.getByRole('dialog')
  await expect(drawer).toContainText('一件商品放在干净的白色背景上')
  await expect(drawer).not.toContainText('素材库')
  expect(calls.archiveRequests()).toEqual([])
  expect(runtimeErrors).toEqual([])
})

test('keeps generated outputs out of new inputs and freezes the output compression policy on submit', async ({
  page,
}, testInfo) => {
  const calls = await installWorkbenchApi(page)

  await page.goto('/#/ai-workbench/assets')
  await expect(
    page.getByText('商品原图 2 · AI 成品 8 · 全部素材 10', {
      exact: true,
    }),
  ).toBeVisible()
  await page.screenshot({
    path: testInfo.outputPath('ai-material-current-product.png'),
    fullPage: true,
  })

  await page.goto('/#/ai-workbench/generate')
  await page
    .getByLabel('即时生成配置')
    .getByRole('button', { name: '素材库', exact: true })
    .click()
  const picker = page.getByRole('dialog')
  await expect(
    picker.getByRole('button', { name: '选择素材 商品图.png' }),
  ).toBeVisible()
  await expect(picker.getByText('历史AI成品.png')).toHaveCount(0)
  await picker.getByRole('button', { name: '选择素材 商品图.png' }).click()
  await picker.getByRole('button', { name: '选择', exact: true }).click()
  await page.getByLabel('提示词').fill('冻结压缩策略')

  const compression = page.getByLabel('生成后压缩至 1000 KB 以下')
  await expect(compression).not.toBeChecked()
  await compression.check()
  await page.getByRole('button', { name: '生成', exact: true }).click()

  await expect.poll(calls.submittedBody).toMatchObject({
    work_mode: 'INSTANT',
    product_asset_ids: [inputAssetId],
    compress_output_under_1000kb: true,
  })

  await page.getByRole('button', { name: '批量生成', exact: true }).click()
  const batchProductList = page.getByTestId('batch-product-list')
  await expect(batchProductList).toContainText('商品原图 2')
  await page.getByRole('button', { name: '选择产品', exact: true }).click()
  const productPicker = page.getByRole('dialog')
  await expect(productPicker).toContainText('手机支架')
  await expect(productPicker).toContainText('商品原图 2')
  await productPicker.screenshot({
    path: testInfo.outputPath('ai-batch-product-picker-dialog.png'),
  })
  await productPicker.getByRole('button', { name: '取消', exact: true }).click()
})

test('keeps a thumbnail visible while a slow AI output detail image loads and survives rapid selection', async ({
  page,
}, testInfo) => {
  const gate = releaseGate()
  const calls = await installWorkbenchApi(page, {
    assetContentGate: gate.promise,
  })

  await page.goto('/#/ai-workbench/assets')
  await page
    .getByRole('navigation', { name: '素材角色' })
    .getByRole('button', { name: 'AI成品 8', exact: true })
    .click()
  const cards = page.getByRole('button', { name: /^查看素材 历史AI成品/ })
  await expect(cards).toHaveCount(8)
  await cards.first().click()

  const inspector = page.getByRole('region', { name: '素材详情' })
  const loadingImage = inspector.locator('.asset-content-image')
  await expect(loadingImage).toHaveAttribute('data-state', 'loading')
  await expect(loadingImage).toHaveAttribute('data-source', 'thumbnail')
  await expect(loadingImage.getByAltText('历史AI成品.png')).toBeVisible()
  await expect(loadingImage.getByRole('status')).toContainText('正在加载原图')

  await cards.nth(1).click()
  await expect(inspector).toContainText('历史AI成品-2.png')
  const fullImage = inspector.locator(
    '.asset-content-image[data-state="ready"][data-source="content"] img',
  )
  await expect(fullImage).toBeVisible()
  const decoded = await fullImage.evaluate((element) => {
    const image = element as HTMLImageElement
    const bounds = image.getBoundingClientRect()
    return {
      complete: image.complete,
      naturalHeight: image.naturalHeight,
      naturalWidth: image.naturalWidth,
      renderedHeight: bounds.height,
      renderedWidth: bounds.width,
    }
  })
  expect(decoded).toMatchObject({
    complete: true,
    naturalHeight: 384,
    naturalWidth: 512,
  })
  expect(decoded.renderedHeight).toBeGreaterThan(0)
  expect(decoded.renderedWidth).toBeGreaterThan(0)
  expect(
    calls
      .assetImageRequests()
      .filter((request) => request.resource === 'content')
      .map((request) => request.assetId),
  ).toEqual(
    expect.arrayContaining([
      generatedProductAssetId,
      generatedProductAssetIds[1],
    ]),
  )

  gate.release()
  await page.screenshot({
    path: testInfo.outputPath('ai-material-detail-full-image.png'),
    fullPage: true,
  })
})

test('shows an explicit retry when a full material detail image fails, then decodes the retry result', async ({
  page,
}) => {
  const calls = await installWorkbenchApi(page, {
    failAssetContentRequests: 1,
  })

  await page.goto('/#/ai-workbench/assets')
  await page
    .getByRole('navigation', { name: '素材角色' })
    .getByRole('button', { name: 'AI成品 8', exact: true })
    .click()
  await page
    .getByRole('button', { name: '查看素材 历史AI成品.png', exact: true })
    .click()

  const inspector = page.getByRole('region', { name: '素材详情' })
  const image = inspector.locator('.asset-content-image')
  await expect(image).toHaveAttribute('data-state', 'error')
  await expect(image).toHaveAttribute('data-source', 'none')
  const retry = image.getByRole('button', {
    name: '重新加载图片：历史AI成品.png',
  })
  await expect(retry).toBeVisible()
  await retry.click()

  const fullImage = inspector.locator(
    '.asset-content-image[data-state="ready"][data-source="content"] img',
  )
  await expect(fullImage).toBeVisible()
  const decoded = await fullImage.evaluate((element) => {
    const image = element as HTMLImageElement
    return {
      complete: image.complete,
      naturalHeight: image.naturalHeight,
      naturalWidth: image.naturalWidth,
    }
  })
  expect(decoded).toEqual({
    complete: true,
    naturalHeight: 384,
    naturalWidth: 512,
  })
  expect(
    calls
      .assetImageRequests()
      .filter(
        (request) =>
          request.assetId === generatedProductAssetId &&
          request.resource === 'content',
      ),
  ).toHaveLength(2)
})

test('updates results in place and never masks a detail read error with a stale spinner', async ({
  page,
}) => {
  test.setTimeout(45_000)
  const calls = await installWorkbenchApi(page, { controlledJob: true })

  await page.goto('/#/ai-workbench/generate')
  await selectInstantSource(page)
  await page.getByLabel('提示词').fill('原地轮询自动出图')
  await page.getByRole('button', { name: '生成', exact: true }).click()
  await expect.poll(calls.submitCount).toBe(1)
  await expect(page.locator('[data-result-status="WAITING"]')).toBeVisible()

  calls.setControlledJobStatus('RUNNING')
  await expect(page.locator('[data-result-status="RUNNING"]')).toBeVisible({
    timeout: 10_000,
  })

  calls.failControlledJobDetail(true)
  await expect(page.getByText('任务读取失败', { exact: true })).toBeVisible({
    timeout: 10_000,
  })
  await expect(page.getByText('生成任务暂时无法读取')).toBeVisible()
  await expect(page.locator('[data-result-status="RUNNING"]')).toHaveCount(0)

  calls.setControlledJobStatus('SUCCESS')
  calls.failControlledJobDetail(false)
  const successCard = page.locator('[data-result-status="SUCCESS"]')
  await expect(successCard).toBeVisible({ timeout: 10_000 })
  await expect(successCard.getByAltText('真实结果.png')).toBeVisible()
  await successCard.getByRole('button', { name: '预览 真实结果.png' }).click()
  await expect(page.getByLabel('图片预览')).toContainText('真实结果.png')
  await expect(
    page.getByLabel('图片预览').getByAltText('真实结果.png'),
  ).toBeVisible()
  expect(calls.submitCount()).toBe(1)
})

test('restores a running job after refresh and a completed result after reopening', async ({
  page,
}) => {
  test.setTimeout(45_000)
  const calls = await installWorkbenchApi(page, { controlledJob: true })

  await page.goto('/#/ai-workbench/generate')
  await selectInstantSource(page)
  await page.getByLabel('提示词').fill('刷新与重开恢复')
  await page.getByRole('button', { name: '生成', exact: true }).click()
  await expect.poll(calls.submitCount).toBe(1)
  calls.setControlledJobStatus('RUNNING')
  await expect(page.locator('[data-result-status="RUNNING"]')).toBeVisible({
    timeout: 10_000,
  })
  const detailReadsBeforeRefresh = calls.jobDetailCount()

  await page.reload()
  await expect(page.getByLabel('提示词')).toHaveValue('刷新与重开恢复')
  await expect(page.getByAltText('商品图.png')).toBeVisible()
  await expect(page.locator('[data-result-status="RUNNING"]')).toBeVisible({
    timeout: 10_000,
  })
  await expect
    .poll(calls.jobDetailCount)
    .toBeGreaterThan(detailReadsBeforeRefresh)
  expect(calls.submitCount()).toBe(1)

  calls.setControlledJobStatus('SUCCESS')
  const successCard = page.locator('[data-result-status="SUCCESS"]')
  await expect(successCard).toBeVisible({ timeout: 10_000 })
  await expect(successCard.getByAltText('真实结果.png')).toBeVisible()

  await page.goto('about:blank')
  await page.goto('/#/ai-workbench/generate')
  await expect(page.getByLabel('提示词')).toHaveValue('刷新与重开恢复')
  await expect(
    page.locator('[data-result-status="SUCCESS"]').getByAltText('真实结果.png'),
  ).toBeVisible({ timeout: 10_000 })
  const restoredCard = page.locator('[data-result-status="SUCCESS"]')
  const download = page.waitForEvent('download')
  await restoredCard.getByRole('button', { name: /下载 真实结果/ }).click()
  await download
  await expect(
    restoredCard.getByRole('button', { name: /更多操作/ }),
  ).toHaveCount(0)
  await expect(page.getByText('保存到素材库', { exact: true })).toHaveCount(0)
  expect(calls.archiveRequests()).toEqual([])
  expect(calls.submitCount()).toBe(1)
})

test('reuses one submission key when refresh interrupts the submit receipt', async ({
  page,
}) => {
  test.setTimeout(45_000)
  const gate = releaseGate()
  const calls = await installWorkbenchApi(page, {
    controlledJob: true,
    submissionGate: gate.promise,
  })

  await page.goto('/#/ai-workbench/generate')
  await selectInstantSource(page)
  await page.getByLabel('提示词').fill('回执中断幂等恢复')
  await page.getByRole('button', { name: '生成', exact: true }).click()
  await expect.poll(calls.submitCount).toBe(1)

  await page.reload()
  await expect.poll(calls.submitCount).toBe(2)
  const submissionKeys = calls
    .submittedBodies()
    .map((body) => body.submission_key)
  expect(new Set(submissionKeys).size).toBe(1)
  expect(calls.submittedBodies()[1]).toEqual(calls.submittedBodies()[0])

  calls.setControlledJobStatus('RUNNING')
  gate.release()
  await expect(page.locator('[data-result-status="RUNNING"]')).toBeVisible({
    timeout: 10_000,
  })
  expect(
    new Set(calls.submittedBodies().map((body) => body.submission_key)).size,
  ).toBe(1)
})

test('clears a running instant task without allowing its late response to return', async ({
  page,
}) => {
  test.setTimeout(45_000)
  const calls = await installWorkbenchApi(page, { controlledJob: true })
  const detailGate = releaseGate()

  await page.goto('/#/ai-workbench/generate')
  await selectInstantSource(page)
  await page.getByLabel('提示词').fill('清空后不得回写')
  await page.getByRole('button', { name: '生成', exact: true }).click()
  await expect.poll(calls.submitCount).toBe(1)
  calls.setControlledJobStatus('RUNNING')
  await expect(page.locator('[data-result-status="RUNNING"]')).toBeVisible({
    timeout: 10_000,
  })

  calls.holdNextJobDetail(detailGate.promise)
  calls.setControlledJobStatus('SUCCESS')
  await expect.poll(calls.heldJobDetailCount).toBe(1)
  await page.getByRole('button', { name: '清空当前任务', exact: true }).click()
  const dialog = page.getByRole('dialog').filter({ hasText: '清空当前任务' })
  await expect(dialog).toContainText(
    '运行中的后台任务不会取消，仍可在生成记录中查看',
  )
  await dialog.getByRole('button', { name: '清空', exact: true }).click()
  detailGate.release()

  await expect(page.getByLabel('提示词')).toHaveValue('')
  await expect(page.locator('[data-result-status]')).toHaveCount(0)
  await expect(page.getByText('暂无生成结果')).toBeVisible()
  await page.reload()
  await expect(page.getByLabel('提示词')).toHaveValue('')
  await expect(page.locator('[data-result-status]')).toHaveCount(0)
  expect(calls.submitCount()).toBe(1)
})

test('renders template and material management from formal API DTOs', async ({
  page,
}) => {
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))
  await installWorkbenchApi(page)

  await page.goto('/#/ai-workbench/templates')
  await expect(
    page.getByText('电商标准套图', { exact: true }).first(),
  ).toBeVisible()
  await expect(page.getByText('纯白主图', { exact: true })).toBeVisible()

  await page
    .getByRole('navigation', { name: 'AI 功能入口' })
    .getByRole('button', { name: '素材库' })
    .click()
  await expect(
    page.getByText('手机支架', { exact: true }).first(),
  ).toBeVisible()
  await expect(page.getByAltText('商品图.png')).toBeVisible()
  await expect(page.getByRole('region', { name: '当前产品素材' })).toBeVisible()

  expect(runtimeErrors).toEqual([])
})

test('retains instant and batch drafts across work-mode and route navigation', async ({
  page,
}) => {
  test.setTimeout(45_000)
  await installWorkbenchApi(page)
  await page.goto('/#/ai-workbench/generate')

  await selectInstantSource(page)
  await page.getByLabel('生成模型').click()
  await page
    .locator('.n-base-select-option:visible')
    .getByText('GPT Image 2 Backup', { exact: true })
    .click()
  await page.getByLabel('生成模板').click()
  await page
    .locator('.n-base-select-option:visible')
    .getByText('纯白主图', { exact: true })
    .click()
  await page.getByLabel('提示词').fill('导航恢复专用提示词')
  await page.getByRole('button', { name: '四宫格', exact: true }).click()
  await page.getByLabel('生成比例').click()
  await page
    .locator('.n-base-select-option:visible')
    .getByText('3:4', { exact: true })
    .click()
  await page.getByLabel('生成数量').locator('input').fill('2')

  await page.getByRole('button', { name: '批量生成', exact: true }).click()
  await page.getByRole('button', { name: '选择产品', exact: true }).click()
  await page.getByRole('button', { name: '选择产品 手机支架' }).click()
  await page
    .getByRole('dialog')
    .getByRole('button', { name: '确定', exact: true })
    .click()
  await page.getByRole('button', { name: '本次选择', exact: true }).click()
  await page.getByLabel('本次模板组').click()
  await page
    .locator('.n-base-select-option:visible')
    .getByText('电商标准套图', { exact: true })
    .click()
  await page.getByRole('button', { name: '仅主图', exact: true }).click()
  await page.getByRole('button', { name: '执行检查', exact: true }).click()

  await page.getByRole('button', { name: '即时生成', exact: true }).click()
  await expect(page.getByAltText('商品图.png')).toBeVisible()
  await expect(page.getByLabel('生成模型')).toContainText('GPT Image 2 Backup')
  await expect(page.getByLabel('生成模板')).toContainText('纯白主图')
  await expect(page.getByLabel('提示词')).toHaveValue('导航恢复专用提示词')
  await expect(page.getByLabel('生成比例')).toContainText('3:4')
  await expect(page.getByLabel('生成数量').locator('input')).toHaveValue('2')
  await expect(
    page.getByRole('button', { name: '四宫格', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true')

  await page
    .getByRole('navigation', { name: 'AI 功能入口' })
    .getByRole('button', { name: '模板库' })
    .click()
  await expect(page).toHaveURL(/#\/ai-workbench\/templates$/)
  await page
    .getByRole('navigation', { name: 'AI 功能入口' })
    .getByRole('button', { name: 'AI生图' })
    .click()
  await expect(page).toHaveURL(/#\/ai-workbench\/generate$/)
  await page.reload()

  await expect(page.getByAltText('商品图.png')).toBeVisible()
  await expect(page.getByLabel('提示词')).toHaveValue('导航恢复专用提示词')
  await page.getByRole('button', { name: '批量生成', exact: true }).click()
  await expect(page.getByTestId('batch-product-list')).toContainText('手机支架')
  await expect(page.getByLabel('本次模板组')).toContainText('电商标准套图')
  await expect(
    page.getByRole('button', { name: '仅主图', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByTestId('batch-preflight')).toBeVisible()
  await page.reload()
  await expect(page.getByLabel('批量生成模型')).toBeVisible()
  await expect(page.getByTestId('batch-product-list')).toContainText('手机支架')
  await expect(page.getByLabel('本次模板组')).toContainText('电商标准套图')
  await expect(page.getByTestId('batch-preflight')).toBeVisible()
})

test('resumes one delayed task after navigation and keeps completed result actions', async ({
  page,
}) => {
  test.setTimeout(45_000)
  const gate = releaseGate()
  const calls = await installWorkbenchApi(page, {
    controlledJob: true,
    submissionGate: gate.promise,
  })
  await page.goto('/#/ai-workbench/generate')
  await selectInstantSource(page)
  await page.getByLabel('提示词').fill('延迟回执状态恢复')
  await page.getByRole('button', { name: '生成', exact: true }).click()
  await expect.poll(calls.submitCount).toBe(1)

  await page
    .getByRole('navigation', { name: 'AI 功能入口' })
    .getByRole('button', { name: '模板库' })
    .click()
  await expect(page).toHaveURL(/#\/ai-workbench\/templates$/)
  calls.setControlledJobStatus('RUNNING')
  gate.release()
  await page
    .getByRole('navigation', { name: 'AI 功能入口' })
    .getByRole('button', { name: 'AI生图' })
    .click()
  await expect(page).toHaveURL(/#\/ai-workbench\/generate$/)

  await expect(page.locator('[data-result-status="RUNNING"]')).toBeVisible({
    timeout: 10_000,
  })
  expect(calls.submitCount()).toBe(1)
  await expect.poll(calls.submittedBody).toMatchObject({
    product_asset_ids: [inputAssetId],
    prompt: '延迟回执状态恢复',
  })

  calls.setControlledJobStatus('SUCCESS')
  const successCard = page.locator('[data-result-status="SUCCESS"]')
  await expect(successCard).toBeVisible({ timeout: 10_000 })
  await expect(successCard.getByAltText('真实结果.png')).toBeVisible()

  await page
    .getByRole('navigation', { name: 'AI 功能入口' })
    .getByRole('button', { name: '素材库' })
    .click()
  await expect(page).toHaveURL(/#\/ai-workbench\/assets$/)
  await page
    .getByRole('navigation', { name: 'AI 功能入口' })
    .getByRole('button', { name: 'AI生图' })
    .click()
  await expect(page).toHaveURL(/#\/ai-workbench\/generate$/)

  const restoredCard = page.locator('[data-result-status="SUCCESS"]')
  await expect(restoredCard.getByAltText('真实结果.png')).toBeVisible()
  const download = page.waitForEvent('download')
  await restoredCard.getByRole('button', { name: /下载 真实结果/ }).click()
  await download
  await expect(
    restoredCard.getByRole('button', { name: /更多操作/ }),
  ).toHaveCount(0)
  await expect(page.getByText('保存到素材库', { exact: true })).toHaveCount(0)
  expect(calls.archiveRequests()).toEqual([])
  expect(calls.submitCount()).toBe(1)
})

test('clears retained workbench state on logout and team change', async ({
  page,
}) => {
  const calls = await installWorkbenchApi(page)
  const waitForModuleAccess = () =>
    page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname ===
          '/api/v1/access-management/me/module-access' &&
        response.status() === 200,
    )
  await page.goto('/#/ai-workbench/generate')
  await page.getByLabel('提示词').fill('登出前草稿')
  await page.getByRole('button', { name: '当前用户菜单' }).click()
  await page.getByText('退出登录', { exact: true }).click()
  await page.getByLabel('内部登录账号').fill('multi-operator')
  await page.getByLabel('密码').fill('safe-test-password')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.locator('.login-card .n-base-selection').click()
  await page.getByText('运营团队', { exact: true }).click()
  const selectedOperationsTeam = waitForModuleAccess()
  await page.getByRole('button', { name: '进入中控台' }).click()
  await selectedOperationsTeam
  await page.goto('/#/ai-workbench/generate')
  await expect(page.getByLabel('提示词')).toHaveValue('')

  await page.getByLabel('提示词').fill('切换团队前草稿')
  await page.getByRole('button', { name: '当前用户菜单' }).click()
  const selectedDefaultTeam = waitForModuleAccess()
  await page.getByText('切换至 默认团队', { exact: true }).click()
  await selectedDefaultTeam
  await expect(page.getByLabel('提示词')).toHaveValue('')
  await page.reload()
  await expect(page.getByLabel('提示词')).toHaveValue('')

  await page.getByLabel('提示词').fill('会话失效前草稿')
  calls.expireSessionOnNextRequest()
  await page
    .getByRole('navigation', { name: 'AI 功能入口' })
    .getByRole('button', { name: '模板库' })
    .click()
  await expect(page).toHaveURL(/#\/login\?redirect=/)
  await page.getByLabel('内部登录账号').fill('operator')
  await page.getByLabel('密码').fill('safe-test-password')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.goto('/#/ai-workbench/generate')
  await expect(page.getByLabel('提示词')).toHaveValue('')
})

test('recovers one multi-product batch job through refresh and renders grouped results in place', async ({
  page,
}) => {
  test.setTimeout(60_000)
  const calls = await installWorkbenchApi(page, {
    controlledJob: true,
    batchScenario: true,
  })
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))

  await submitControlledBatch(page)
  await expect.poll(calls.submitCount).toBe(1)
  await expect.poll(calls.submittedBody).toMatchObject({
    work_mode: 'BATCH',
    model_id: modelId,
    mode: 'NORMAL_GENERATION',
    product_scope: 'ALL_ENABLED',
    selected_product_ids: [],
    template_source: 'PRODUCT_CONFIGURED',
    selected_template_group_ids: [],
    output_range: 'ALL',
  })

  calls.setControlledJobStatus('RUNNING')
  const summary = page.getByTestId('batch-execution-summary')
  await expect(summary).toContainText('生成中', { timeout: 10_000 })
  await expect(summary).toContainText('1 / 4')
  await expect(page.getByTestId('batch-product-task-row')).toHaveCount(2)
  const detailReadsBeforeRefresh = calls.jobDetailCount()

  await page.reload()
  await expect(page.getByLabel('批量生成模型')).toBeVisible()
  await expect(page.getByTestId('batch-execution-summary')).toContainText(
    '生成中',
    { timeout: 10_000 },
  )
  await expect(page.getByTestId('batch-product-task-row')).toHaveCount(2)
  await expect
    .poll(calls.jobDetailCount)
    .toBeGreaterThan(detailReadsBeforeRefresh)
  expect(calls.submitCount()).toBe(1)

  calls.setControlledJobStatus('SUCCESS')
  await expect(page.getByTestId('batch-execution-summary')).toContainText(
    '已完成',
    { timeout: 10_000 },
  )
  await expect(page.getByTestId('batch-execution-summary')).toContainText(
    '4 / 4',
  )

  let detail = await selectBatchProduct(page, materialGroup.name)
  await expandBatchTemplateGroup(page, templateGroup.name)
  await expect(
    detail
      .locator(`[data-template-id="${templateId}"]`)
      .getByAltText('纯白主图 结果 1'),
  ).toBeVisible()
  await expandBatchTemplateGroup(page, detailTemplateGroup.name)
  await expect(
    detail
      .locator(`[data-template-id="${detailTemplateId}"]`)
      .getByAltText('细节展示 结果 1'),
  ).toBeVisible()

  detail = await selectBatchProduct(page, secondMaterialGroup.name)
  await expandBatchTemplateGroup(page, templateGroup.name)
  await expect(
    detail
      .locator(`[data-template-id="${templateId}"]`)
      .getByAltText('纯白主图 结果 1'),
  ).toBeVisible()
  await expandBatchTemplateGroup(page, detailTemplateGroup.name)
  await expect(
    detail
      .locator(`[data-template-id="${detailTemplateId}"]`)
      .getByAltText('细节展示 结果 1'),
  ).toBeVisible()

  await page.reload()
  await expect(page.getByTestId('batch-execution-summary')).toContainText(
    '4 / 4',
    { timeout: 10_000 },
  )
  await expect(page.getByTestId('batch-product-task-row')).toHaveCount(2)
  await page.goto('about:blank')
  await page.goto('/#/ai-workbench/generate')
  await expect(page.getByLabel('批量生成模型')).toBeVisible()
  await expect(page.getByTestId('batch-execution-summary')).toContainText(
    '4 / 4',
    { timeout: 10_000 },
  )
  expect(calls.submitCount()).toBe(1)

  detail = await selectBatchProduct(page, materialGroup.name)
  await expandBatchTemplateGroup(page, templateGroup.name)
  const outputAssetIds = new Set<string>(
    batchItemFixtures.map((fixture) => fixture.outputAssetId),
  )
  const outputRequestCount = () =>
    calls
      .assetContentRequests()
      .filter((assetId) => outputAssetIds.has(assetId)).length
  const requestsBeforeTemplateDownload = outputRequestCount()
  const templateDownload = page.waitForEvent('download')
  await detail
    .getByRole('button', { name: '下载 纯白主图', exact: true })
    .click()
  await templateDownload
  await expect.poll(outputRequestCount).toBe(requestsBeforeTemplateDownload + 1)

  const downloadedFilenames: string[] = []
  page.on('download', (download) => {
    downloadedFilenames.push(download.suggestedFilename())
  })
  const requestsBeforeDownloadAll = outputRequestCount()
  const perAssetRequestsBeforeDownloadAll = new Map(
    [...outputAssetIds].map((assetId) => [
      assetId,
      calls.assetContentRequests().filter((candidate) => candidate === assetId)
        .length,
    ]),
  )
  await page.getByRole('button', { name: '下载全部', exact: true }).click()
  await expect.poll(outputRequestCount).toBe(requestsBeforeDownloadAll + 4)
  for (const assetId of outputAssetIds) {
    await expect
      .poll(
        () =>
          calls
            .assetContentRequests()
            .filter((candidate) => candidate === assetId).length,
      )
      .toBe((perAssetRequestsBeforeDownloadAll.get(assetId) ?? 0) + 1)
  }
  await expect.poll(() => downloadedFilenames.length).toBe(4)
  expect(downloadedFilenames.every((name) => name.endsWith('.png'))).toBe(true)
  expect(downloadedFilenames.some((name) => name.endsWith('.zip'))).toBe(false)
  expect(runtimeErrors).toEqual([])
})

test('scopes generation-record detail downloads to the clicked single, group, or batch', async ({
  page,
}) => {
  test.setTimeout(60_000)
  const calls = await installWorkbenchApi(page, {
    controlledJob: true,
    batchScenario: true,
  })
  const outputAssetIds = new Set(
    batchItemFixtures.map((fixture) => fixture.outputAssetId),
  )
  const outputRequestCount = () =>
    calls
      .assetContentRequests()
      .filter((assetId) => outputAssetIds.has(assetId)).length
  const outputRequestsSince = (count: number) =>
    calls
      .assetContentRequests()
      .filter((assetId) => outputAssetIds.has(assetId))
      .slice(count)

  await submitControlledBatch(page)
  await expect.poll(calls.submitCount).toBe(1)
  calls.setControlledJobStatus('SUCCESS')
  await expect(page.getByTestId('batch-execution-summary')).toContainText(
    '已完成',
    { timeout: 10_000 },
  )

  await page
    .getByRole('navigation', { name: 'AI 功能入口' })
    .getByRole('button', { name: '生成记录' })
    .click()
  await page
    .getByLabel('生成记录列表')
    .getByRole('button', { name: '查看', exact: true })
    .click()
  const drawer = page.getByRole('dialog')
  await expect(drawer.getByTestId('batch-result-tree')).toBeVisible()
  const previewButtons = drawer.getByRole('button', { name: /^预览 / })
  await expect(previewButtons).toHaveCount(4)
  for (let index = 0; index < 4; index += 1) {
    await previewButtons.nth(index).scrollIntoViewIfNeeded()
  }
  await expect(drawer.locator('img')).toHaveCount(4)
  await expect
    .poll(async () =>
      drawer
        .locator('img')
        .evaluateAll((images) =>
          images.every((image) => image.complete && image.naturalWidth > 0),
        ),
    )
    .toBe(true)

  const beforeSingle = outputRequestCount()
  const singleDownload = page.waitForEvent('download')
  await drawer
    .getByRole('button', {
      name: `下载 ${batchItemFixtures[1]!.outputFilename}`,
      exact: true,
    })
    .click()
  await singleDownload
  await expect.poll(outputRequestCount).toBe(beforeSingle + 1)
  expect(outputRequestsSince(beforeSingle)).toEqual([
    batchItemFixtures[1]!.outputAssetId,
  ])

  const beforeGroup = outputRequestCount()
  const groupDownload = page.waitForEvent('download')
  await drawer
    .getByRole('button', {
      name: `下载 ${templateGroup.name} 结果`,
      exact: true,
    })
    .first()
    .click()
  await groupDownload
  await expect.poll(outputRequestCount).toBe(beforeGroup + 1)
  expect(outputRequestsSince(beforeGroup)).toEqual([
    batchItemFixtures[0]!.outputAssetId,
  ])

  const beforeBatch = outputRequestCount()
  const downloads: string[] = []
  page.on('download', (download) =>
    downloads.push(download.suggestedFilename()),
  )
  await drawer.getByRole('button', { name: '下载整个批次' }).click()
  await expect.poll(outputRequestCount).toBe(beforeBatch + 4)
  expect(outputRequestsSince(beforeBatch)).toEqual(
    batchItemFixtures.map((fixture) => fixture.outputAssetId),
  )
  await expect.poll(() => downloads.length).toBe(4)
})

test('restores partial-failed batch hierarchy and its actions after refresh and reopening', async ({
  page,
}) => {
  test.setTimeout(60_000)
  const calls = await installWorkbenchApi(page, {
    controlledJob: true,
    batchScenario: true,
  })

  await submitControlledBatch(page)
  await expect.poll(calls.submitCount).toBe(1)
  calls.setControlledJobStatus('PARTIAL_FAILED')
  await expect(page.getByTestId('batch-execution-summary')).toContainText(
    '部分失败',
    { timeout: 10_000 },
  )
  await expect(page.getByTestId('batch-execution-summary')).toContainText(
    '4 / 4',
  )

  await page.reload()
  await expect(page.getByTestId('batch-execution-summary')).toContainText(
    '部分失败',
    { timeout: 10_000 },
  )
  await page.goto('about:blank')
  await page.goto('/#/ai-workbench/generate')
  await expect(page.getByLabel('批量生成模型')).toBeVisible()
  await expect(page.getByTestId('batch-execution-summary')).toContainText(
    '部分失败',
    { timeout: 10_000 },
  )

  for (const productName of [materialGroup.name, secondMaterialGroup.name]) {
    const detail = await selectBatchProduct(page, productName)
    await expandBatchTemplateGroup(page, detailTemplateGroup.name)
    const failedCard = detail.locator(
      `[data-template-id="${detailTemplateId}"]`,
    )
    await expect(
      failedCard.locator('[data-result-status="FAILED"]'),
    ).toBeVisible()
    await expect(
      failedCard.getByRole('button', {
        name: '重试 细节展示',
        exact: true,
      }),
    ).toBeVisible()
    await expandBatchTemplateGroup(page, templateGroup.name)
    const successCard = detail.locator(`[data-template-id="${templateId}"]`)
    await expect(
      successCard.getByRole('button', {
        name: '下载 纯白主图',
        exact: true,
      }),
    ).toBeVisible()
  }
  await expect(
    page.getByRole('button', { name: '下载全部', exact: true }),
  ).toBeVisible()
  expect(calls.submitCount()).toBe(1)
})

test('reuses the original batch request and submission key when refresh interrupts its receipt', async ({
  page,
}) => {
  test.setTimeout(60_000)
  const gate = releaseGate()
  const calls = await installWorkbenchApi(page, {
    controlledJob: true,
    batchScenario: true,
    submissionGate: gate.promise,
  })

  await submitControlledBatch(page)
  await expect.poll(calls.submitCount).toBe(1)
  await page.reload()
  await expect.poll(calls.submitCount).toBe(2)
  expect(calls.submittedBodies()[1]).toEqual(calls.submittedBodies()[0])
  expect(
    new Set(calls.submittedBodies().map((body) => body.submission_key)).size,
  ).toBe(1)

  calls.setControlledJobStatus('RUNNING')
  gate.release()
  await expect(page.getByTestId('batch-execution-summary')).toContainText(
    '生成中',
    { timeout: 10_000 },
  )
  const submitCountAfterReceipt = calls.submitCount()
  await page.reload()
  await expect(page.getByTestId('batch-execution-summary')).toContainText(
    '生成中',
    { timeout: 10_000 },
  )
  expect(calls.submitCount()).toBe(submitCountAfterReceipt)
  expect(
    new Set(calls.submittedBodies().map((body) => body.submission_key)).size,
  ).toBe(1)
})

test('clears only the batch task and rejects its late response without deleting history or assets', async ({
  page,
}) => {
  test.setTimeout(60_000)
  const calls = await installWorkbenchApi(page, {
    controlledJob: true,
    batchScenario: true,
  })
  const detailGate = releaseGate()

  await page.goto('/#/ai-workbench/generate')
  await page.getByLabel('提示词').fill('即时草稿不受批量清空影响')
  await page.getByRole('button', { name: '批量生成', exact: true }).click()
  await page.getByRole('button', { name: '执行检查', exact: true }).click()
  await page.getByRole('button', { name: '开始生成', exact: true }).click()
  await expect.poll(calls.submitCount).toBe(1)
  calls.setControlledJobStatus('RUNNING')
  await expect(page.getByTestId('batch-execution-summary')).toContainText(
    '生成中',
    { timeout: 10_000 },
  )

  calls.holdNextJobDetail(detailGate.promise)
  calls.setControlledJobStatus('SUCCESS')
  await expect.poll(calls.heldJobDetailCount).toBe(1)
  await page.getByRole('button', { name: '清空当前任务', exact: true }).click()
  const dialog = page.getByRole('dialog').filter({ hasText: '清空当前任务' })
  await expect(dialog).toContainText(
    '运行中的后台任务不会取消，仍可在生成记录中查看',
  )
  await dialog.getByRole('button', { name: '清空', exact: true }).click()
  detailGate.release()

  await expect(page.getByTestId('batch-execution-viewer')).toContainText(
    '暂无生成结果',
  )
  await expect(page.getByTestId('batch-product-task-row')).toHaveCount(0)
  await page.reload()
  await expect(page.getByTestId('batch-execution-viewer')).toContainText(
    '暂无生成结果',
  )
  await page.getByRole('button', { name: '即时生成', exact: true }).click()
  await expect(page.getByLabel('提示词')).toHaveValue(
    '即时草稿不受批量清空影响',
  )

  await page
    .getByRole('navigation', { name: 'AI 功能入口' })
    .getByRole('button', { name: '生成记录' })
    .click()
  const records = page.getByLabel('生成记录列表')
  await expect(records).toContainText('批量生成')
  await records.getByRole('button', { name: '查看', exact: true }).click()
  const drawer = page.getByRole('dialog')
  await expect(drawer).toContainText(materialGroup.name)
  await expect(drawer).toContainText(secondMaterialGroup.name)
  await expect(drawer).toContainText(templateGroup.name)
  await expect(drawer).toContainText(detailTemplateGroup.name)
  expect(calls.destructiveRequests()).toEqual([])
  expect(calls.submitCount()).toBe(1)
})

test('shows a retryable batch read error instead of keeping stale running results', async ({
  page,
}) => {
  test.setTimeout(60_000)
  const calls = await installWorkbenchApi(page, {
    controlledJob: true,
    batchScenario: true,
  })

  await submitControlledBatch(page)
  await expect.poll(calls.submitCount).toBe(1)
  calls.setControlledJobStatus('RUNNING')
  await expect(page.getByTestId('batch-execution-summary')).toContainText(
    '生成中',
    { timeout: 10_000 },
  )

  calls.failControlledJobDetail(true)
  await expect(page.getByText('任务读取失败', { exact: true })).toBeVisible({
    timeout: 15_000,
  })
  await expect(page.getByText('生成任务暂时无法读取')).toBeVisible()
  await expect(page.getByTestId('batch-execution-viewer')).toHaveCount(0)

  calls.setControlledJobStatus('SUCCESS')
  calls.failControlledJobDetail(false)
  await page.getByRole('button', { name: '重新加载', exact: true }).click()
  await expect(page.getByTestId('batch-execution-summary')).toContainText(
    '已完成',
    { timeout: 10_000 },
  )
  await expect(page.getByTestId('batch-execution-summary')).toContainText(
    '4 / 4',
  )
  expect(calls.submitCount()).toBe(1)
})
