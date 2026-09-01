import { createProductMaterialGroupFixtures } from '../../assets/__fixtures__/product-material-groups.fixture'
import { createTemplateGroupFixtures } from '../../templates/__fixtures__/template-groups.fixture'
import { createGenerationVisualMockFixture } from '../__fixtures__/generation.fixture'
import type {
  GenerationProductView,
  GenerationSourceImageView,
  GenerationTemplateGroupView,
  GenerationVisualMockFixture,
} from './types'

function mapProducts(): GenerationProductView[] {
  return createProductMaterialGroupFixtures().map((product) => ({
    id: product.id,
    name: product.name,
    enabled: product.enabled,
    normalGenerationEnabled: product.normalGenerationEnabled,
    styleReplicationEnabled: product.styleReplicationEnabled,
    normalTemplateGroupIds: [...product.normalTemplateGroupIds],
    styleReplicationTemplateGroupIds: [
      ...product.styleReplicationTemplateGroupIds,
    ],
    assets: product.assets
      .filter(
        (
          asset,
        ): asset is typeof asset & {
          role: GenerationSourceImageView['role']
        } =>
          asset.role === 'PRODUCT_SOURCE' || asset.role === 'STYLE_REFERENCE',
      )
      .map((asset) => ({
        id: asset.assetId,
        name: asset.name,
        previewUrl: asset.previewUrl,
        role: asset.role,
        sourceType: 'ASSET_LIBRARY',
        productId: product.id,
        productName: product.name,
      })),
  }))
}

function mapTemplateGroups(): GenerationTemplateGroupView[] {
  return createTemplateGroupFixtures().map((group) => ({
    id: group.id,
    name: group.name,
    mode: group.mode,
    enabled: group.enabled,
    templates: group.templates.map((template) => ({
      id: template.id,
      groupId: group.id,
      groupName: group.name,
      name: template.name,
      mode: group.mode,
      enabled: template.enabled,
      outputRole: template.outputRole,
      outputFormat: template.outputFormat,
      size: template.size,
      count: template.count,
      prompt: template.prompt,
      sortOrder: template.sortOrder,
    })),
  }))
}

export function loadAiGenerationVisualMock(): GenerationVisualMockFixture {
  return createGenerationVisualMockFixture(mapProducts(), mapTemplateGroups())
}
