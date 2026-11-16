export const GENERATION_OUTPUT_FORMATS = ['SINGLE', 'COLLAGE_2X2'] as const

export type GenerationOutputFormat = (typeof GENERATION_OUTPUT_FORMATS)[number]

export const GENERATION_OUTPUT_FORMAT_META: Record<
  GenerationOutputFormat,
  { label: string }
> = {
  SINGLE: { label: '单图' },
  COLLAGE_2X2: { label: '四宫格' },
}

export const GENERATION_SIZE_OPTIONS = ['1:1', '3:4', '4:3', '16:9'] as const

export type GenerationSize = (typeof GENERATION_SIZE_OPTIONS)[number]

export interface GenerationConfig {
  prompt: string
  outputFormat: GenerationOutputFormat
  size: GenerationSize
  count: number
}

export function cloneGenerationConfig(
  config: GenerationConfig,
): GenerationConfig {
  return {
    prompt: config.prompt,
    outputFormat: config.outputFormat,
    size: config.size,
    count: config.count,
  }
}
