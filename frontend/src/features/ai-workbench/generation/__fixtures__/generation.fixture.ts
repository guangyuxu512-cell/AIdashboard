import type {
  BatchProductResultView,
  GenerationExecutionResultView,
  GenerationProductView,
  GenerationRecordStatus,
  GenerationRecordView,
  GenerationResultView,
  GenerationTemplateGroupView,
  GenerationVisualMockFixture,
} from '../model/types'
import { cloneGenerationConfig } from '../../shared/model/generation-config'

export const GENERATION_VISUAL_FIXTURE_MARKER =
  'AI_GENERATION_VISUAL_FIXTURE_0106'

const FIXTURE_CREATED_BY = ['张三', '李雪', '王晨'] as const

function createPreviewUrl(index: number, label: string): string {
  const palettes = [
    ['#4f6f91', '#263544'],
    ['#8b7e74', '#3c4048'],
    ['#789395', '#405458'],
    ['#a47551', '#5c4033'],
  ] as const
  const palette = palettes[index % palettes.length] ?? palettes[0]
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="960" height="960" viewBox="0 0 960 960">
      <defs>
        <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="${palette[0]}"/>
          <stop offset="1" stop-color="${palette[1]}"/>
        </linearGradient>
      </defs>
      <rect width="960" height="960" rx="64" fill="url(#g)"/>
      <circle cx="760" cy="180" r="150" fill="#fff" opacity=".08"/>
      <rect x="250" y="180" width="460" height="510" rx="72" fill="#fff" opacity=".92"/>
      <rect x="320" y="250" width="320" height="320" rx="44" fill="#202834" opacity=".86"/>
      <rect x="390" y="620" width="180" height="28" rx="14" fill="#cbd5e1"/>
      <text x="480" y="790" text-anchor="middle" fill="#fff" font-size="42" font-weight="700" font-family="Arial, 'Microsoft YaHei', sans-serif">${label}</text>
      <text x="480" y="842" text-anchor="middle" fill="#fff" opacity=".72" font-size="26" font-family="Arial, sans-serif">0${index + 1}</text>
    </svg>`
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}

function cloneProducts(
  products: readonly GenerationProductView[],
): GenerationProductView[] {
  return products.map((product) => ({
    ...product,
    normalTemplateGroupIds: [...product.normalTemplateGroupIds],
    styleReplicationTemplateGroupIds: [
      ...product.styleReplicationTemplateGroupIds,
    ],
    assets: product.assets.map((asset) => ({ ...asset })),
  }))
}

function cloneTemplateGroups(
  groups: readonly GenerationTemplateGroupView[],
): GenerationTemplateGroupView[] {
  const batchCountOverrides: Readonly<Record<string, number>> = {
    'normal-standard-main-2': 2,
    'normal-standard-detail-2': 4,
    'normal-life-2': 2,
  }
  return groups.map((group) => ({
    ...group,
    templates: group.templates.map((template) => ({
      ...template,
      count: batchCountOverrides[template.id] ?? template.count,
    })),
  }))
}

function createScaleProducts(
  sourceProduct: GenerationProductView | undefined,
): GenerationProductView[] {
  if (!sourceProduct) return []
  return Array.from({ length: 12 }, (_, index) => {
    const suffix = String(index + 1).padStart(2, '0')
    const productId = `generation-scale-product-${suffix}`
    const productName = `批量商品 ${suffix}`
    return {
      ...sourceProduct,
      id: productId,
      name: productName,
      normalTemplateGroupIds: [...sourceProduct.normalTemplateGroupIds],
      styleReplicationTemplateGroupIds: [
        ...sourceProduct.styleReplicationTemplateGroupIds,
      ],
      assets: sourceProduct.assets.map((asset) => ({
        ...asset,
        id: `${productId}-${asset.id}`,
        productId,
        productName,
      })),
    }
  })
}

function createEdgeCaseGroups(): GenerationTemplateGroupView[] {
  const templateBase = {
    mode: 'NORMAL_GENERATION' as const,
    outputRole: 'MAIN_IMAGE' as const,
    outputFormat: 'SINGLE' as const,
    size: '1:1' as const,
    count: 1,
    prompt: '商品主体清晰，纯色背景，避免模糊和变形。',
    sortOrder: 1,
  }
  return [
    {
      id: 'generation-disabled-group',
      name: '停用模板组样例',
      mode: 'NORMAL_GENERATION',
      enabled: false,
      templates: [
        {
          ...templateBase,
          id: 'generation-disabled-group-template',
          groupId: 'generation-disabled-group',
          groupName: '停用模板组样例',
          name: '停用组主图',
          enabled: true,
        },
      ],
    },
    {
      id: 'generation-no-enabled-template',
      name: '停用模板样例',
      mode: 'NORMAL_GENERATION',
      enabled: true,
      templates: [
        {
          ...templateBase,
          id: 'generation-disabled-template',
          groupId: 'generation-no-enabled-template',
          groupName: '停用模板样例',
          name: '已停用主图',
          enabled: false,
        },
      ],
    },
  ]
}

function createEdgeCaseProducts(
  sourceProduct: GenerationProductView | undefined,
): GenerationProductView[] {
  const sourceAsset = sourceProduct?.assets.find(
    (asset) => asset.role === 'PRODUCT_SOURCE',
  )
  const assets = sourceAsset ? [{ ...sourceAsset, productId: undefined }] : []
  const base = {
    enabled: true,
    normalGenerationEnabled: true,
    styleReplicationEnabled: false,
    styleReplicationTemplateGroupIds: [] as string[],
  }
  return [
    {
      ...base,
      id: 'generation-product-no-source',
      name: '耳机样品',
      normalTemplateGroupIds: ['normal-minimal-main'],
      assets: [],
    },
    {
      ...base,
      id: 'generation-product-disabled-group',
      name: '台灯样品',
      normalTemplateGroupIds: ['generation-disabled-group'],
      assets: assets.map((asset) => ({
        ...asset,
        id: 'generation-product-disabled-group-source',
        productId: 'generation-product-disabled-group',
        productName: '台灯样品',
      })),
    },
    {
      ...base,
      id: 'generation-product-no-enabled-template',
      name: '键盘样品',
      normalTemplateGroupIds: ['generation-no-enabled-template'],
      assets: assets.map((asset) => ({
        ...asset,
        id: 'generation-product-no-enabled-template-source',
        productId: 'generation-product-no-enabled-template',
        productName: '键盘样品',
      })),
    },
  ]
}

function result(
  id: string,
  previewUrl: string,
  status: 'SUCCESS' | 'FAILED' = 'SUCCESS',
  size: GenerationResultView['size'] = '1:1',
): GenerationResultView {
  return {
    id,
    name: `${id}.webp`,
    previewUrl,
    status,
    outputRole: 'MAIN_IMAGE',
    size,
  }
}

function batchHierarchy(
  previewUrls: readonly string[],
  group: GenerationTemplateGroupView | undefined,
  status: GenerationRecordStatus,
): BatchProductResultView[] {
  const template = group?.templates.find((candidate) => candidate.enabled)
  if (!group || !template) return []
  const resultStatuses: GenerationResultView['status'][] =
    status === 'PARTIAL_FAILED'
      ? ['SUCCESS', 'FAILED']
      : [status === 'FAILED' ? 'FAILED' : 'SUCCESS']
  return [
    {
      productId: 'pmg-phone-stand',
      productName: '手机支架',
      groups: [
        {
          groupId: group.id,
          groupName: group.name,
          templates: [
            {
              templateId: template.id,
              templateName: template.name,
              outputRole: template.outputRole,
              results: resultStatuses.map((resultStatus, index) =>
                result(
                  `batch-${resultStatus.toLowerCase()}-result-${index + 1}`,
                  previewUrls[index + 1] ?? previewUrls[0] ?? '',
                  resultStatus,
                  template.size,
                ),
              ),
            },
          ],
        },
      ],
    },
  ]
}

function createRecordFixtures(
  products: readonly GenerationProductView[],
  templateGroups: readonly GenerationTemplateGroupView[],
  previewUrls: readonly string[],
): GenerationRecordView[] {
  const product =
    products.find((candidate) => candidate.id === 'pmg-phone-stand') ??
    products[0]
  const productImage = product?.assets.find(
    (asset) => asset.role === 'PRODUCT_SOURCE',
  ) ?? {
    id: 'generation-record-source',
    name: '商品图.webp',
    previewUrl: previewUrls[0] ?? '',
    role: 'PRODUCT_SOURCE' as const,
    sourceType: 'ASSET_LIBRARY' as const,
  }
  const styleReference = product?.assets.find(
    (asset) => asset.role === 'STYLE_REFERENCE',
  )

  const statuses: GenerationRecordStatus[] = [
    'SUCCESS',
    'PARTIAL_FAILED',
    'RUNNING',
    'FAILED',
    'SUCCESS',
  ]

  return Array.from({ length: 25 }, (_, index): GenerationRecordView => {
    const sourceType = index % 3 === 1 ? 'BATCH' : 'INSTANT'
    const mode = index % 4 === 2 ? 'STYLE_REPLICATION' : 'NORMAL_GENERATION'
    const status = statuses[index % statuses.length] ?? 'SUCCESS'
    const createdAt = new Date(
      Date.UTC(2026, 7, 31, 13, 36 - index),
    ).toISOString()
    if (sourceType === 'BATCH') {
      const group = templateGroups.find(
        (candidate) =>
          candidate.mode === mode &&
          candidate.enabled &&
          candidate.templates.some((template) => template.enabled),
      )
      const results = batchHierarchy(previewUrls, group, status)
      const resultItems = results.flatMap((productResult) =>
        productResult.groups.flatMap((groupResult) =>
          groupResult.templates.flatMap(
            (templateResult) => templateResult.results,
          ),
        ),
      )
      const failedCount = resultItems.filter(
        (resultItem) => resultItem.status === 'FAILED',
      ).length
      const successCount = resultItems.length - failedCount
      return {
        id: `generation-record-batch-${index + 1}`,
        sourceType,
        mode,
        status,
        createdAt,
        createdBy: FIXTURE_CREATED_BY[index % FIXTURE_CREATED_BY.length]!,
        summary:
          results.length === 1
            ? results[0]!.productName
            : `${results.length} 个产品`,
        resultSummary:
          failedCount > 0
            ? `${successCount} 成功 · ${failedCount} 失败`
            : `${successCount} 张`,
        detail: {
          kind: 'BATCH',
          productCount: results.length,
          templateGroupCount: results.reduce(
            (total, productResult) => total + productResult.groups.length,
            0,
          ),
          generationItemCount: resultItems.length,
          successCount,
          failedCount,
          results,
        },
      }
    }
    const template =
      index % 2 === 0
        ? (templateGroups
            .find((group) => group.mode === mode && group.enabled)
            ?.templates.find((candidate) => candidate.enabled) ?? null)
        : null
    const effectiveConfig = template
      ? cloneGenerationConfig(template)
      : {
          prompt:
            '商品主体清晰，纯色背景，柔和光线，避免模糊、变形和多余文字。',
          outputFormat: 'SINGLE' as const,
          size: '1:1' as const,
          count: 1,
        }
    const results: GenerationExecutionResultView[] = Array.from(
      { length: effectiveConfig.count },
      (_, offset) => ({
        ...result(
          `generation-record-instant-result-${index + 1}-${offset + 1}`,
          previewUrls[(index + offset) % previewUrls.length] ??
            previewUrls[0] ??
            '',
          status === 'FAILED' ? 'FAILED' : 'SUCCESS',
          effectiveConfig.size,
        ),
        slotIndex: offset,
      }),
    )
    return {
      id: `generation-record-instant-${index + 1}`,
      sourceType,
      mode,
      status,
      createdAt,
      createdBy: FIXTURE_CREATED_BY[index % FIXTURE_CREATED_BY.length]!,
      summary: product?.name ?? '临时生成',
      resultSummary: status === 'FAILED' ? '0 成功 · 1 失败' : '1 张',
      detail: {
        kind: 'INSTANT',
        executionId: `generation-record-instant-execution-${index + 1}`,
        inputSlots: [
          {
            key: 'PRODUCT_IMAGES',
            label: '商品图片',
            images: [{ ...productImage }],
          },
          ...(mode === 'STYLE_REPLICATION' && styleReference
            ? [
                {
                  key: 'REFERENCE_IMAGES' as const,
                  label: '参考图片',
                  images: [{ ...styleReference }],
                },
              ]
            : []),
        ],
        templateId: template?.id ?? null,
        templateName: template?.name ?? null,
        effectiveConfig,
        results,
      },
    }
  }).reverse()
}

export function createGenerationVisualMockFixture(
  frozenProducts: readonly GenerationProductView[],
  frozenTemplateGroups: readonly GenerationTemplateGroupView[],
): GenerationVisualMockFixture {
  const resultPreviewUrls = Array.from({ length: 8 }, (_, index) =>
    createPreviewUrl(index, '生成结果'),
  )
  const products = cloneProducts(frozenProducts)
  products.push(...createScaleProducts(products[0]))
  products.push(...createEdgeCaseProducts(products[0]))
  const templateGroups = cloneTemplateGroups(frozenTemplateGroups)
  templateGroups.push(...createEdgeCaseGroups())
  return {
    products,
    templateGroups,
    records: createRecordFixtures(products, templateGroups, resultPreviewUrls),
    resultPreviewUrls,
  }
}
