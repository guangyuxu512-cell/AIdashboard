import { expect, test, type Page } from '@playwright/test'

import type {
  GenerationItemReadDto,
  GenerationJobReadDto,
  ProductMaterialGroupReadDto,
  TemplateGroupReadDto,
} from '../src/entities/ai-workbench'

test.skip(
  process.env.PLAYWRIGHT_API_MODE === 'real',
  'Intercepted Real API UI contract coverage',
)

const modelId = '11111111-1111-4111-8111-111111111111'
const alternateModelId = '11111111-1111-4111-8111-111111111112'
const groupId = '22222222-2222-4222-8222-222222222222'
const templateId = '33333333-3333-4333-8333-333333333333'
const materialGroupId = '44444444-4444-4444-8444-444444444444'
const inputAssetId = '55555555-5555-4555-8555-555555555555'
const jobId = '66666666-6666-4666-8666-666666666666'
const itemId = '77777777-7777-4777-8777-777777777777'
const outputAssetId = '88888888-8888-4888-8888-888888888888'
const timestamp = '2026-09-06T00:00:00Z'

interface WorkbenchApiOptions {
  controlledJob?: boolean
  submissionGate?: Promise<void>
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
  ],
  template_bindings: [
    {
      material_group_id: materialGroupId,
      template_group_id: groupId,
      generation_mode: 'NORMAL_GENERATION',
      position: 0,
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

async function installWorkbenchApi(
  page: Page,
  options: WorkbenchApiOptions = {},
) {
  let phase: 'initial' | 'retry' | 'success' = 'initial'
  let controlledJobStatus: 'PENDING' | 'RUNNING' | 'SUCCESS' = 'PENDING'
  let pollCount = 0
  let submitCount = 0
  let archived = false
  let expireNextRequest = false
  let submittedBody: Record<string, unknown> | null = null
  let retryBody: Record<string, unknown> | null = null
  let archiveBody: Record<string, unknown> | null = null

  await page.route('**/api/v1/assets/*/content', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'image/png',
      body: Buffer.from(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
        'base64',
      ),
    })
  })

  await page.route('**/api/v1/ai-workbench/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

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
      await route.fulfill({
        json: {
          items: [
            {
              template_group_id: groupId,
              name: templateGroup.name,
              mode: templateGroup.mode,
              enabled: true,
              created_at: timestamp,
              updated_at: timestamp,
            },
          ],
          total: 1,
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
    if (path.endsWith('/product-material-groups') && method === 'GET') {
      await route.fulfill({
        json: {
          items: [
            {
              material_group_id: materialGroupId,
              name: materialGroup.name,
              enabled: true,
              normal_generation_enabled: true,
              style_replication_enabled: false,
              created_at: timestamp,
              updated_at: timestamp,
            },
          ],
          total: 1,
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
      await route.fulfill({ json: materialGroup })
      return
    }
    if (path.endsWith('/generation-jobs') && method === 'POST') {
      submitCount += 1
      submittedBody = request.postDataJSON() as Record<string, unknown>
      pollCount = 0
      if (options.submissionGate) await options.submissionGate
      await route.fulfill({
        status: 202,
        json: generationJob('PENDING', 'PENDING'),
      })
      return
    }
    if (path.endsWith('/generation-jobs') && method === 'GET') {
      const completed = generationJob('SUCCESS', 'SUCCESS', 2, true)
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
      if (options.controlledJob) {
        const itemStatus =
          controlledJobStatus === 'SUCCESS'
            ? 'SUCCESS'
            : controlledJobStatus === 'RUNNING'
              ? 'RUNNING'
              : 'PENDING'
        await route.fulfill({
          json: generationJob(controlledJobStatus, itemStatus, 1, archived),
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
    if (path.endsWith(`/items/${itemId}/archive`) && method === 'POST') {
      archiveBody = request.postDataJSON() as Record<string, unknown>
      phase = 'success'
      archived = true
      await route.fulfill({
        json: generationJob('SUCCESS', 'SUCCESS', 2, true),
      })
      return
    }
    await route.fulfill({
      status: 500,
      json: { code: 'UNHANDLED_TEST_ROUTE', message: `${method} ${path}` },
    })
  })

  return {
    submitCount: () => submitCount,
    submittedBody: () => submittedBody,
    retryBody: () => retryBody,
    archiveBody: () => archiveBody,
    setControlledJobStatus: (status: 'PENDING' | 'RUNNING' | 'SUCCESS') => {
      controlledJobStatus = status
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

test('runs the production workbench through submit, polling, retry, result, archive and records', async ({
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

  await successCard.getByRole('button', { name: /更多操作/ }).click()
  await page
    .locator('.n-dropdown-option:visible')
    .getByText('保存到素材库', { exact: true })
    .click()
  await page.getByLabel('目标产品素材组').click()
  await page
    .locator('.n-base-select-option:visible')
    .getByText('手机支架', { exact: true })
    .click()
  await page
    .getByRole('dialog')
    .getByRole('button', { name: '保存到素材库', exact: true })
    .click()
  await expect.poll(calls.archiveBody).toEqual({
    material_group_id: materialGroupId,
  })
  await expect(successCard).toContainText('已加入素材库')

  await page
    .getByRole('navigation', { name: 'AI 功能入口' })
    .getByRole('button', { name: '生成记录' })
    .click()
  await expect(page.getByLabel('生成记录列表')).toContainText('GPT Image 2')
  await expect(page.getByLabel('搜索生成记录')).toHaveCount(0)
  await page.getByRole('button', { name: '查看' }).click()
  const drawer = page.getByRole('dialog')
  await expect(drawer).toContainText('一件商品放在干净的白色背景上')
  await expect(drawer).toContainText('已加入素材库')
  expect(runtimeErrors).toEqual([])
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

  await expect(page.getByAltText('商品图.png')).toBeVisible()
  await expect(page.getByLabel('提示词')).toHaveValue('导航恢复专用提示词')
  await page.getByRole('button', { name: '批量生成', exact: true }).click()
  await expect(page.getByTestId('batch-product-list')).toContainText('手机支架')
  await expect(page.getByLabel('本次模板组')).toContainText('电商标准套图')
  await expect(
    page.getByRole('button', { name: '仅主图', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true')
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
  await restoredCard.getByRole('button', { name: /更多操作/ }).click()
  await page
    .locator('.n-dropdown-option:visible')
    .getByText('保存到素材库', { exact: true })
    .click()
  await page.getByLabel('目标产品素材组').click()
  await page
    .locator('.n-base-select-option:visible')
    .getByText('手机支架', { exact: true })
    .click()
  await page
    .getByRole('dialog')
    .getByRole('button', { name: '保存到素材库', exact: true })
    .click()
  await expect.poll(calls.archiveBody).toEqual({
    material_group_id: materialGroupId,
  })
  expect(calls.submitCount()).toBe(1)
})

test('clears retained workbench state on logout and team change', async ({
  page,
}) => {
  const calls = await installWorkbenchApi(page)
  await page.goto('/#/ai-workbench/generate')
  await page.getByLabel('提示词').fill('登出前草稿')
  await page.getByRole('button', { name: '当前用户菜单' }).click()
  await page.getByText('退出登录', { exact: true }).click()
  await page.getByLabel('内部登录账号').fill('multi-operator')
  await page.getByLabel('密码').fill('safe-test-password')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.locator('.login-card .n-base-selection').click()
  await page.getByText('运营团队', { exact: true }).click()
  await page.getByRole('button', { name: '进入中控台' }).click()
  await page.goto('/#/ai-workbench/generate')
  await expect(page.getByLabel('提示词')).toHaveValue('')

  await page.getByLabel('提示词').fill('切换团队前草稿')
  await page.getByRole('button', { name: '当前用户菜单' }).click()
  await page.getByText('切换至 默认团队', { exact: true }).click()
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
