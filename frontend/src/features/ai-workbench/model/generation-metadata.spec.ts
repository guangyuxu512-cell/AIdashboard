import { describe, expect, it } from 'vitest'

import {
  GENERATION_OUTPUT_FORMAT_META,
  GENERATION_OUTPUT_ROLE_META,
  GENERATION_RECORD_SOURCE_TYPE_META,
  GENERATION_WORK_MODE_META,
} from '../generation/model/types'
import { GENERATION_MODE_META as SHARED_GENERATION_MODE_META } from '../shared/model/generation-mode'
import {
  GENERATION_MODE_META as TEMPLATE_GENERATION_MODE_META,
  TEMPLATE_OUTPUT_FORMAT_META,
  TEMPLATE_OUTPUT_ROLE_META,
} from '../templates/model/types'

describe('AI generation metadata source of truth', () => {
  it('shares mode, output and work-mode presentation metadata', () => {
    expect(TEMPLATE_GENERATION_MODE_META).toBe(SHARED_GENERATION_MODE_META)
    expect(TEMPLATE_OUTPUT_FORMAT_META).toBe(GENERATION_OUTPUT_FORMAT_META)
    expect(TEMPLATE_OUTPUT_ROLE_META).toBe(GENERATION_OUTPUT_ROLE_META)
    expect(GENERATION_RECORD_SOURCE_TYPE_META).toBe(GENERATION_WORK_MODE_META)
  })
})
