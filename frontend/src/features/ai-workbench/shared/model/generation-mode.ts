export const GENERATION_MODE_ORDER = [
  'NORMAL_GENERATION',
  'STYLE_REPLICATION',
] as const

export type GenerationMode = (typeof GENERATION_MODE_ORDER)[number]

export const GENERATION_MODE_META: Record<GenerationMode, { label: string }> = {
  NORMAL_GENERATION: { label: '普通生图' },
  STYLE_REPLICATION: { label: '风格复刻' },
}
