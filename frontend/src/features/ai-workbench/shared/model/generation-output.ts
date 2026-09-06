export type GenerationOutputRole = 'MAIN_IMAGE' | 'DETAIL_IMAGE'

export const GENERATION_OUTPUT_ROLE_META: Record<
  GenerationOutputRole,
  { label: string }
> = {
  MAIN_IMAGE: { label: '主图' },
  DETAIL_IMAGE: { label: '详情' },
}
