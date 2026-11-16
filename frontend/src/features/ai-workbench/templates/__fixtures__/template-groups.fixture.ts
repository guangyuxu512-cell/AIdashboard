import type {
  GenerationMode,
  PromptTemplate,
  TemplateGroup,
  TemplateOutputFormat,
  TemplateOutputRole,
  TemplateSize,
} from '../model/types'

const FIXTURE_TIMESTAMP = '2026-08-31T00:00:00.000Z'

interface TemplateFixtureInput {
  id: string
  name: string
  sortOrder: number
  outputRole?: TemplateOutputRole
  outputFormat?: TemplateOutputFormat
  size?: TemplateSize
  count?: number
  variables?: string[]
  prompt?: string
  enabled?: boolean
}

const DEFAULT_PROMPT_RESTRICTIONS = '避免模糊、变形、多余文字和低清晰度'

function withPromptRestrictions(prompt: string): string {
  const normalized = prompt.trim().replace(/[。.]$/, '')
  return `${normalized}，${DEFAULT_PROMPT_RESTRICTIONS}。`
}

function template(input: TemplateFixtureInput): PromptTemplate {
  return {
    id: input.id,
    name: input.name,
    enabled: input.enabled ?? true,
    outputRole: input.outputRole ?? 'MAIN_IMAGE',
    outputFormat: input.outputFormat ?? 'SINGLE',
    size: input.size ?? '1:1',
    count: input.count ?? 1,
    variables: input.variables ?? ['product_name', 'selling_points'],
    prompt: withPromptRestrictions(
      input.prompt ??
        '{product_name}，突出{selling_points}，商品主体清晰，画面干净。',
    ),
    sortOrder: input.sortOrder,
    createdAt: FIXTURE_TIMESTAMP,
    updatedAt: FIXTURE_TIMESTAMP,
  }
}

function group(
  id: string,
  name: string,
  mode: GenerationMode,
  templates: PromptTemplate[],
  enabled = true,
): TemplateGroup {
  return {
    id,
    name,
    mode,
    enabled,
    templates,
    createdAt: FIXTURE_TIMESTAMP,
    updatedAt: FIXTURE_TIMESTAMP,
  }
}

function standardSetTemplates(): PromptTemplate[] {
  const coreTemplates: PromptTemplate[] = [
    template({
      id: 'normal-standard-main-1',
      name: '极简白底',
      sortOrder: 1,
      prompt: '{product_name}，极简白底主图，突出{selling_points}。',
    }),
    template({
      id: 'normal-standard-main-2',
      name: '场景展示',
      sortOrder: 2,
      size: '3:4',
      variables: ['product_name', 'scenes'],
      prompt: '{product_name}置于{scenes}，自然光线，主体清晰。',
    }),
    template({
      id: 'normal-standard-main-3',
      name: '卖点构图',
      sortOrder: 3,
      outputFormat: 'COLLAGE_2X2',
      prompt: '{product_name}卖点构图，突出{selling_points}。',
    }),
    template({
      id: 'normal-standard-detail-1',
      name: '核心卖点',
      sortOrder: 4,
      outputRole: 'DETAIL_IMAGE',
      size: '3:4',
    }),
    template({
      id: 'normal-standard-detail-2',
      name: '产品细节',
      sortOrder: 5,
      outputRole: 'DETAIL_IMAGE',
      size: '3:4',
      variables: ['product_name', 'product_details'],
      prompt: '{product_name}细节特写，呈现{product_details}。',
    }),
    template({
      id: 'normal-standard-detail-3',
      name: '参数信息',
      sortOrder: 6,
      outputRole: 'DETAIL_IMAGE',
      size: '3:4',
      variables: ['product_name', 'product_parameters'],
      prompt: '{product_name}参数信息版式，展示{product_parameters}。',
    }),
    template({
      id: 'normal-standard-detail-4',
      name: '品牌收尾',
      sortOrder: 7,
      outputRole: 'DETAIL_IMAGE',
      size: '3:4',
      variables: ['product_name', 'brand_name'],
      prompt: '{brand_name}品牌收尾画面，搭配{product_name}。',
    }),
  ]

  const extendedTemplates = Array.from({ length: 17 }, (_, index) => {
    const sortOrder = index + 8
    return template({
      id: `normal-standard-extension-${String(index + 1).padStart(2, '0')}`,
      name: `场景扩展 ${String(index + 1).padStart(2, '0')}`,
      sortOrder,
      outputRole: index % 2 === 0 ? 'MAIN_IMAGE' : 'DETAIL_IMAGE',
      size: index % 3 === 0 ? '3:4' : '1:1',
      variables: ['product_name', 'scenes'],
      prompt: '{product_name}场景扩展，环境为{scenes}。',
    })
  })

  return [...coreTemplates, ...extendedTemplates]
}

export function createTemplateGroupFixtures(): TemplateGroup[] {
  return [
    group(
      'normal-standard-set',
      '电商标准套图 A',
      'NORMAL_GENERATION',
      standardSetTemplates(),
    ),
    group('normal-minimal-main', '极简主图组', 'NORMAL_GENERATION', [
      template({
        id: 'normal-minimal-1',
        name: '纯白正面主图',
        sortOrder: 1,
      }),
      template({
        id: 'normal-minimal-2',
        name: '轻阴影侧面主图',
        sortOrder: 2,
      }),
      template({
        id: 'normal-minimal-3',
        name: '结构细节主图',
        sortOrder: 3,
      }),
      template({
        id: 'normal-minimal-4',
        name: '尺寸对比详情',
        sortOrder: 4,
        outputRole: 'DETAIL_IMAGE',
      }),
    ]),
    group('normal-lifestyle-set', '生活场景套图', 'NORMAL_GENERATION', [
      template({ id: 'normal-life-1', name: '客厅场景', sortOrder: 1 }),
      template({ id: 'normal-life-2', name: '办公场景', sortOrder: 2 }),
      template({ id: 'normal-life-3', name: '户外场景', sortOrder: 3 }),
      template({
        id: 'normal-life-4',
        name: '使用步骤',
        sortOrder: 4,
        outputRole: 'DETAIL_IMAGE',
      }),
      template({
        id: 'normal-life-5',
        name: '场景收尾',
        sortOrder: 5,
        outputRole: 'DETAIL_IMAGE',
      }),
    ]),
    group('normal-new-product-detail', '新品详情套图', 'NORMAL_GENERATION', [
      template({
        id: 'normal-new-detail-1',
        name: '新品首屏',
        sortOrder: 1,
        outputRole: 'DETAIL_IMAGE',
      }),
      template({
        id: 'normal-new-detail-2',
        name: '卖点拆解',
        sortOrder: 2,
        outputRole: 'DETAIL_IMAGE',
      }),
      template({
        id: 'normal-new-detail-3',
        name: '材质细节',
        sortOrder: 3,
        outputRole: 'DETAIL_IMAGE',
      }),
      template({
        id: 'normal-new-detail-4',
        name: '参数收尾',
        sortOrder: 4,
        outputRole: 'DETAIL_IMAGE',
      }),
    ]),
    group('style-competitor-a', '竞品复刻 A', 'STYLE_REPLICATION', [
      template({
        id: 'style-competitor-main',
        name: '竞品主图复刻',
        sortOrder: 1,
        variables: ['product_name', 'reference_image'],
        prompt: '{product_name}参考{reference_image}的构图与光影。',
      }),
      template({
        id: 'style-competitor-detail',
        name: '竞品详情复刻',
        sortOrder: 2,
        outputRole: 'DETAIL_IMAGE',
        size: '3:4',
        variables: ['product_name', 'reference_image'],
        prompt: '{product_name}参考{reference_image}的详情版式。',
      }),
    ]),
    group('style-minimal-replication', '极简风格复刻', 'STYLE_REPLICATION', [
      template({
        id: 'style-minimal-main',
        name: '极简主图复刻',
        sortOrder: 1,
        variables: ['product_name', 'reference_image'],
      }),
    ]),
    group('style-scene-replication', '场景复刻组', 'STYLE_REPLICATION', [
      template({
        id: 'style-scene-main',
        name: '场景主图复刻',
        sortOrder: 1,
        variables: ['product_name', 'reference_image', 'scenes'],
      }),
      template({
        id: 'style-scene-detail',
        name: '场景详情复刻',
        sortOrder: 2,
        outputRole: 'DETAIL_IMAGE',
        size: '3:4',
        variables: ['product_name', 'reference_image', 'scenes'],
      }),
    ]),
  ]
}
