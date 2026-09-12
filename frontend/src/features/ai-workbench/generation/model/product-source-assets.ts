import type {
  GenerationProductAssetView,
  GenerationProductView,
  GenerationSourceImageView,
} from './types'

/**
 * Generated output is a product-material fact, not a future generation input.
 * Keep the product-source selection in one place so displayed counts and
 * batch preflight use the same input boundary.
 */
export function getGenerationProductSourceAssets(
  assets: readonly GenerationProductAssetView[],
): GenerationSourceImageView[] {
  return assets.filter(
    (asset): asset is GenerationSourceImageView =>
      asset.role === 'PRODUCT_SOURCE',
  )
}

export function countGenerationProductSourceAssets(
  product: Pick<GenerationProductView, 'assets'>,
): number {
  return getGenerationProductSourceAssets(product.assets).length
}
