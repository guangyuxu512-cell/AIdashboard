import type {
  GenerationMode,
  MaterialAssetReference,
  MaterialRole,
  ProductMaterialGroup,
} from '../model/types'

interface FixtureAssetInput {
  product: string
  filename: string
  role: MaterialRole
  index: number
  palette: readonly [string, string]
  generationMode?: GenerationMode
}

function createPreviewUrl({
  product,
  role,
  index,
  palette,
}: FixtureAssetInput): string {
  const roleMark =
    role === 'PRODUCT_SOURCE'
      ? 'SOURCE'
      : role === 'STYLE_REFERENCE'
        ? 'STYLE'
        : 'AI'
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="800" height="800" viewBox="0 0 800 800">
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="${palette[0]}"/>
          <stop offset="1" stop-color="${palette[1]}"/>
        </linearGradient>
        <filter id="shadow" x="-30%" y="-30%" width="160%" height="160%">
          <feDropShadow dx="0" dy="24" stdDeviation="22" flood-color="#111827" flood-opacity=".2"/>
        </filter>
      </defs>
      <rect width="800" height="800" rx="52" fill="url(#bg)"/>
      <circle cx="662" cy="142" r="112" fill="#fff" opacity=".12"/>
      <circle cx="132" cy="668" r="168" fill="#fff" opacity=".08"/>
      <g filter="url(#shadow)">
        <rect x="235" y="172" width="330" height="410" rx="56" fill="#fff" opacity=".94"/>
        <rect x="286" y="225" width="228" height="244" rx="28" fill="#1f2937" opacity=".88"/>
        <rect x="338" y="506" width="124" height="24" rx="12" fill="#cbd5e1"/>
      </g>
      <rect x="52" y="52" width="126" height="42" rx="21" fill="#111827" opacity=".72"/>
      <text x="115" y="80" text-anchor="middle" fill="#fff" font-size="18" font-family="Arial, sans-serif" letter-spacing="2">${roleMark}</text>
      <text x="400" y="676" text-anchor="middle" fill="#fff" font-size="42" font-weight="700" font-family="Arial, 'Microsoft YaHei', sans-serif">${product}</text>
      <text x="400" y="722" text-anchor="middle" fill="#fff" opacity=".72" font-size="22" font-family="Arial, sans-serif">0${index}</text>
    </svg>`

  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}

function createAsset(input: FixtureAssetInput): MaterialAssetReference {
  const extension = input.filename.split('.').pop()?.toLowerCase()
  const mediaType =
    extension === 'png'
      ? 'image/png'
      : extension === 'webp'
        ? 'image/webp'
        : 'image/jpeg'

  return {
    assetId: `fixture-${input.product}-${input.role}-${input.index}`,
    name: input.filename,
    mediaType,
    sourceType:
      input.role === 'AI_OUTPUT' ? 'AI_GENERATION' : 'MATERIAL_IMPORT',
    role: input.role,
    previewUrl: createPreviewUrl(input),
    width: 1600,
    height: 1600,
    sizeBytes: 420_000 + input.index * 73_000,
    generationMode: input.generationMode,
  }
}

function createAssets(
  product: string,
  role: MaterialRole,
  filenames: readonly string[],
  palette: readonly [string, string],
  modes: readonly GenerationMode[] = [],
): MaterialAssetReference[] {
  return filenames.map((filename, index) =>
    createAsset({
      product,
      filename,
      role,
      index: index + 1,
      palette,
      generationMode: modes[index],
    }),
  )
}

function createProduct(
  input: Omit<ProductMaterialGroup, 'createdAt' | 'updatedAt'>,
): ProductMaterialGroup {
  return {
    ...input,
    createdAt: '2026-08-18T09:00:00.000Z',
    updatedAt: '2026-08-28T16:30:00.000Z',
  }
}

const PHONE_STAND_SOURCE_FILENAMES = [
  '正面.jpg',
  '侧面.jpg',
  '折叠态.png',
  '桌面场景.webp',
  '包装图.jpg',
  ...Array.from(
    { length: 26 },
    (_, index) => `商品素材-${String(index + 6).padStart(2, '0')}.jpg`,
  ),
]

export function createProductMaterialGroupFixtures(): ProductMaterialGroup[] {
  return [
    createProduct({
      id: 'pmg-phone-stand',
      name: '手机支架',
      enabled: true,
      normalGenerationEnabled: true,
      styleReplicationEnabled: true,
      normalTemplateGroupIds: ['normal-standard-set', 'normal-lifestyle-set'],
      styleReplicationTemplateGroupIds: [
        'style-competitor-a',
        'style-scene-replication',
      ],
      assets: [
        ...createAssets(
          '手机支架',
          'PRODUCT_SOURCE',
          PHONE_STAND_SOURCE_FILENAMES,
          ['#526d82', '#27374d'],
        ),
        ...createAssets(
          '手机支架',
          'STYLE_REFERENCE',
          ['参考-极简白底.jpg', '参考-桌面场景.jpg', '参考-金属质感.webp'],
          ['#8e9eab', '#425466'],
        ),
        ...createAssets(
          '手机支架',
          'AI_OUTPUT',
          [
            '主图-01.webp',
            '主图-02.webp',
            '主图-03.webp',
            '复刻-01.webp',
            '复刻-02.webp',
            '复刻-03.webp',
          ],
          ['#64748b', '#334155'],
          [
            'NORMAL_GENERATION',
            'NORMAL_GENERATION',
            'NORMAL_GENERATION',
            'STYLE_REPLICATION',
            'STYLE_REPLICATION',
            'STYLE_REPLICATION',
          ],
        ),
      ],
    }),
    createProduct({
      id: 'pmg-mug',
      name: '马克杯',
      enabled: true,
      normalGenerationEnabled: true,
      styleReplicationEnabled: false,
      normalTemplateGroupIds: ['normal-minimal-main'],
      styleReplicationTemplateGroupIds: ['style-minimal-replication'],
      assets: [
        ...createAssets(
          '马克杯',
          'PRODUCT_SOURCE',
          ['杯身正面.jpg', '杯口细节.jpg', '握柄细节.png', '包装.webp'],
          ['#a47551', '#5c4033'],
        ),
        ...createAssets(
          '马克杯',
          'AI_OUTPUT',
          ['主图-暖调.webp', '主图-冷调.webp'],
          ['#b08968', '#6f4e37'],
          ['NORMAL_GENERATION', 'NORMAL_GENERATION'],
        ),
      ],
    }),
    createProduct({
      id: 'pmg-ring',
      name: '戒指',
      enabled: false,
      normalGenerationEnabled: true,
      styleReplicationEnabled: true,
      normalTemplateGroupIds: ['normal-lifestyle-set'],
      styleReplicationTemplateGroupIds: ['style-scene-replication'],
      assets: [
        ...createAssets(
          '戒指',
          'PRODUCT_SOURCE',
          ['正视图.jpg', '侧视图.jpg', '佩戴图.webp'],
          ['#8b7e74', '#3c4048'],
        ),
        ...createAssets(
          '戒指',
          'STYLE_REFERENCE',
          ['参考-珠宝台.jpg', '参考-丝绒背景.webp'],
          ['#7c6f64', '#302b32'],
        ),
        ...createAssets(
          '戒指',
          'AI_OUTPUT',
          ['成品-01.webp', '成品-02.webp', '成品-03.webp', '成品-04.webp'],
          ['#786f80', '#34313a'],
          [
            'NORMAL_GENERATION',
            'NORMAL_GENERATION',
            'STYLE_REPLICATION',
            'STYLE_REPLICATION',
          ],
        ),
      ],
    }),
    createProduct({
      id: 'pmg-storage-box',
      name: '收纳盒',
      enabled: true,
      normalGenerationEnabled: true,
      styleReplicationEnabled: true,
      normalTemplateGroupIds: ['normal-new-product-detail'],
      styleReplicationTemplateGroupIds: [],
      assets: [
        ...createAssets(
          '收纳盒',
          'PRODUCT_SOURCE',
          ['展开图.jpg', '叠放图.webp'],
          ['#5f7161', '#2f4538'],
        ),
        ...createAssets(
          '收纳盒',
          'STYLE_REFERENCE',
          ['参考-家居场景.jpg'],
          ['#789395', '#405458'],
        ),
      ],
    }),
    createProduct({
      id: 'pmg-thermos',
      name: '保温杯',
      enabled: true,
      normalGenerationEnabled: true,
      styleReplicationEnabled: true,
      normalTemplateGroupIds: ['normal-standard-set'],
      styleReplicationTemplateGroupIds: ['style-competitor-a'],
      assets: [
        ...createAssets(
          '保温杯',
          'PRODUCT_SOURCE',
          ['正面.jpg', '杯盖.jpg', '杯底.jpg', '户外场景.webp', '包装.jpg'],
          ['#4f5d75', '#242c3a'],
        ),
        ...createAssets(
          '保温杯',
          'AI_OUTPUT',
          ['成品-01.webp', '成品-02.webp', '成品-03.webp'],
          ['#536976', '#292e49'],
          ['NORMAL_GENERATION', 'NORMAL_GENERATION', 'NORMAL_GENERATION'],
        ),
      ],
    }),
  ]
}
