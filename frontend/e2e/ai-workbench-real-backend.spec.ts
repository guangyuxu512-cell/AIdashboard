import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

import { expect, test } from '@playwright/test'

test.skip(
  process.env.PLAYWRIGHT_API_MODE !== 'real',
  'Real Backend AI Workbench coverage',
)
test.describe.configure({ mode: 'serial' })

const frontendDirectory = path.dirname(fileURLToPath(import.meta.url))
const backendDirectory = path.resolve(frontendDirectory, '../../backend')
const backendPython = path.join(
  backendDirectory,
  '.venv',
  'Scripts',
  'python.exe',
)
const teamId = '91111111-1111-4111-8111-111111111111'
const userId = '92222222-2222-4222-8222-222222222222'
const membershipId = '93333333-3333-4333-8333-333333333333'
const loginName = 'ai-real-api-e2e'
const password = 'ai-real-api-e2e-password'
const namePrefix = 'ai-real-api-e2e-'
const runPaidGeneration = process.env.AI_REAL_GENERATION_E2E === '1'

function runBackendScript(lines: string[]): void {
  execFileSync(backendPython, ['-c', lines.join('\n')], {
    cwd: backendDirectory,
    stdio: 'pipe',
  })
}

function cleanupFixtures(): void {
  runBackendScript([
    'from uuid import UUID',
    'from sqlalchemy import delete, select',
    'from sqlalchemy.orm import Session',
    'from app.core.config import get_settings',
    'from app.core.database import get_database_engine',
    'from app.modules.access.models import MembershipModuleAccess, Team, TeamMembership',
    'from app.modules.ai_workbench.models import GenerationItem, GenerationItemAsset, GenerationJob, GenerationProviderExecution, MaterialGroupAsset, MaterialGroupTemplateBinding, ProductMaterialGroup, PromptTemplate, TemplateGroup',
    'from app.modules.assets.models import Asset',
    'from app.modules.assets.storage import LocalAssetStorage',
    'from app.modules.human_auth.models import HumanSession',
    'from app.modules.users.models import User',
    `team_id = UUID(${JSON.stringify(teamId)})`,
    `user_id = UUID(${JSON.stringify(userId)})`,
    'with Session(get_database_engine()) as session:',
    '    job_ids = list(session.scalars(select(GenerationJob.generation_job_id).where(GenerationJob.created_by_user_id == user_id)))',
    '    if job_ids:',
    '        item_ids = list(session.scalars(select(GenerationItem.generation_item_id).where(GenerationItem.generation_job_id.in_(job_ids))))',
    '        if item_ids:',
    '            session.execute(delete(GenerationProviderExecution).where(GenerationProviderExecution.generation_item_id.in_(item_ids)))',
    '            session.execute(delete(GenerationItemAsset).where(GenerationItemAsset.generation_item_id.in_(item_ids)))',
    '            session.execute(delete(GenerationItem).where(GenerationItem.generation_item_id.in_(item_ids)))',
    '        session.execute(delete(GenerationJob).where(GenerationJob.generation_job_id.in_(job_ids)))',
    '    material_ids = list(session.scalars(select(ProductMaterialGroup.material_group_id).where(ProductMaterialGroup.created_by_user_id == user_id)))',
    '    template_ids = list(session.scalars(select(TemplateGroup.template_group_id).where(TemplateGroup.created_by_user_id == user_id)))',
    '    if material_ids:',
    '        session.execute(delete(MaterialGroupTemplateBinding).where(MaterialGroupTemplateBinding.material_group_id.in_(material_ids)))',
    '        session.execute(delete(MaterialGroupAsset).where(MaterialGroupAsset.material_group_id.in_(material_ids)))',
    '        session.execute(delete(ProductMaterialGroup).where(ProductMaterialGroup.material_group_id.in_(material_ids)))',
    '    if template_ids:',
    '        session.execute(delete(MaterialGroupTemplateBinding).where(MaterialGroupTemplateBinding.template_group_id.in_(template_ids)))',
    '        session.execute(delete(PromptTemplate).where(PromptTemplate.template_group_id.in_(template_ids)))',
    '        session.execute(delete(TemplateGroup).where(TemplateGroup.template_group_id.in_(template_ids)))',
    '    assets = list(session.scalars(select(Asset).where(Asset.created_by_user_id == user_id)))',
    '    storage = LocalAssetStorage(get_settings().asset_storage_dir, get_settings().asset_max_upload_bytes)',
    '    for asset in assets:',
    '        storage.delete(asset.storage_key)',
    '        session.delete(asset)',
    '    session.execute(delete(HumanSession).where(HumanSession.user_id == user_id))',
    '    session.execute(delete(MembershipModuleAccess).where(MembershipModuleAccess.membership_id == UUID(' +
      JSON.stringify(membershipId) +
      ')))',
    '    session.execute(delete(TeamMembership).where(TeamMembership.user_id == user_id))',
    '    session.execute(delete(User).where(User.user_id == user_id))',
    '    session.execute(delete(Team).where(Team.team_id == team_id))',
    '    session.commit()',
  ])
}

function seedHumanAccess(): void {
  cleanupFixtures()
  runBackendScript([
    'from uuid import UUID',
    'from sqlalchemy.orm import Session',
    'from app.core.database import get_database_engine',
    'from app.modules.access.models import MembershipModuleAccess, Team, TeamMembership',
    'from app.modules.human_auth.passwords import PasswordService',
    'from app.modules.users.models import User',
    `team_id = UUID(${JSON.stringify(teamId)})`,
    `user_id = UUID(${JSON.stringify(userId)})`,
    `membership_id = UUID(${JSON.stringify(membershipId)})`,
    `password = ${JSON.stringify(password)}`,
    'with Session(get_database_engine()) as session:',
    `    session.add(Team(team_id=team_id, name=${JSON.stringify(`${namePrefix}team`)}, enabled=True))`,
    `    session.add(User(user_id=user_id, display_name=${JSON.stringify(`${namePrefix}user`)}, login_name=${JSON.stringify(loginName)}, password_hash=PasswordService().hash_password(password), enabled=True))`,
    '    session.flush()',
    '    session.add(TeamMembership(membership_id=membership_id, team_id=team_id, user_id=user_id, role_code="member", data_scope="team", enabled=True))',
    '    session.flush()',
    '    session.add_all([MembershipModuleAccess(membership_id=membership_id, module_code="ai-workbench"), MembershipModuleAccess(membership_id=membership_id, module_code="asset")])',
    '    session.commit()',
  ])
}

test.beforeAll(seedHumanAccess)
test.afterAll(cleanupFixtures)

test('connects the production UI to the real model, template, material and generation APIs', async ({
  page,
}) => {
  test.setTimeout(runPaidGeneration ? 300_000 : 45_000)
  await page.goto('/#/ai-workbench/generate')
  await expect(page).toHaveURL(/#\/login/)
  await page.getByLabel('内部登录账号').fill(loginName)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/#\/ai-workbench\/generate$/)

  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))

  const modelsResponse = await page.request.get('/api/v1/ai-workbench/models')
  expect(modelsResponse.status()).toBe(200)
  const models = (await modelsResponse.json()) as Array<{
    model_id: string
    display_name: string
    is_default: boolean
  }>
  const defaultModel = models.find((model) => model.is_default)
  expect(defaultModel).toBeTruthy()

  const templateGroupResponse = await page.request.post(
    '/api/v1/ai-workbench/template-groups',
    {
      data: {
        name: `${namePrefix}templates`,
        mode: 'NORMAL_GENERATION',
        enabled: true,
      },
    },
  )
  expect(templateGroupResponse.status()).toBe(201)
  const templateGroup = (await templateGroupResponse.json()) as {
    template_group_id: string
  }
  const promptResponse = await page.request.post(
    `/api/v1/ai-workbench/template-groups/${templateGroup.template_group_id}/prompt-templates`,
    {
      data: {
        name: `${namePrefix}main`,
        enabled: true,
        output_role: 'MAIN_IMAGE',
        output_format: 'SINGLE',
        size: '1:1',
        count: 1,
        variables: [],
        prompt: 'A simple product on a clean white background',
      },
    },
  )
  expect(promptResponse.status()).toBe(201)

  const materialResponse = await page.request.post(
    '/api/v1/ai-workbench/product-material-groups',
    {
      data: {
        name: `${namePrefix}product`,
        enabled: true,
        normal_generation_enabled: true,
        style_replication_enabled: false,
      },
    },
  )
  expect(materialResponse.status()).toBe(201)
  const material = (await materialResponse.json()) as {
    material_group_id: string
  }
  const assetResponse = await page.request.post('/api/v1/assets', {
    multipart: {
      file: {
        name: `${namePrefix}product.png`,
        mimeType: 'image/png',
        buffer: readFileSync(
          path.resolve(
            frontendDirectory,
            '../src/assets/brand/siyu-ai-mark.png',
          ),
        ),
      },
    },
  })
  expect(assetResponse.status()).toBe(201)
  const asset = (await assetResponse.json()) as { asset_id: string }
  expect(
    (
      await page.request.post(
        `/api/v1/ai-workbench/product-material-groups/${material.material_group_id}/assets`,
        { data: { asset_id: asset.asset_id, role: 'PRODUCT_SOURCE' } },
      )
    ).status(),
  ).toBe(200)
  expect(
    (
      await page.request.put(
        `/api/v1/ai-workbench/product-material-groups/${material.material_group_id}/template-bindings/NORMAL_GENERATION`,
        { data: { template_group_ids: [templateGroup.template_group_id] } },
      )
    ).status(),
  ).toBe(200)

  await page.reload()
  await expect(page.getByLabel('生成模型')).toContainText(
    defaultModel!.display_name,
  )
  await page
    .getByLabel('即时生成配置')
    .getByRole('button', { name: '素材库', exact: true })
    .click()
  await page
    .getByRole('button', { name: `选择素材 ${namePrefix}product.png` })
    .click()
  await page
    .getByRole('dialog')
    .getByRole('button', { name: '选择', exact: true })
    .click()
  await page
    .getByLabel('提示词')
    .fill('A simple product on a clean white background')

  const submitResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname ===
        '/api/v1/ai-workbench/generation-jobs',
  )
  await page.getByRole('button', { name: '生成', exact: true }).click()
  const submitResponse = await submitResponsePromise
  expect(submitResponse.status()).toBe(202)
  const job = (await submitResponse.json()) as {
    generation_job_id: string
    model_id: string
    status: string
  }
  expect(job).toMatchObject({
    model_id: defaultModel!.model_id,
    status: 'PENDING',
  })
  if (runPaidGeneration) {
    const successCard = page.locator('[data-result-status="SUCCESS"]')
    await expect(successCard).toBeVisible({ timeout: 240_000 })
    const resultImage = successCard.locator('img')
    await expect(resultImage).toHaveAttribute('src', /^blob:/)
    await expect
      .poll(() => resultImage.evaluate((image) => image.naturalWidth))
      .toBeGreaterThan(0)

    const completedResponse = await page.request.get(
      `/api/v1/ai-workbench/generation-jobs/${job.generation_job_id}`,
    )
    expect(completedResponse.status()).toBe(200)
    const completed = (await completedResponse.json()) as GenerationJobReadDto
    expect(completed).toMatchObject({
      status: 'SUCCESS',
      success_count: 1,
      failed_count: 0,
      items: [{ status: 'SUCCESS' }],
    })
    expect(completed.items[0]?.output_asset?.source_type).toBe('ai_generated')
  } else {
    await expect(page.locator('[data-result-status="WAITING"]')).toBeVisible()
  }

  await page
    .getByRole('navigation', { name: 'AI 功能入口' })
    .getByRole('button', { name: '生成记录' })
    .click()
  await expect(page.getByLabel('生成记录列表')).toContainText(
    defaultModel!.display_name,
  )
  await page.getByRole('button', { name: '查看' }).click()
  await expect(page.getByRole('dialog')).toContainText(
    'A simple product on a clean white background',
  )
  if (runPaidGeneration) {
    await expect(
      page.getByRole('dialog').locator('[data-result-status="SUCCESS"] img'),
    ).toBeVisible()
  }

  expect(runtimeErrors).toEqual([])
})
