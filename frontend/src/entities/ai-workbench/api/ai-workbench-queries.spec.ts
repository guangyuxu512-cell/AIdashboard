import { describe, expect, it } from 'vitest'

import type {
  GenerationJobPageDto,
  GenerationJobSummaryReadDto,
} from './contracts'
import {
  generationJobListPollingInterval,
  generationJobPollingInterval,
} from './ai-workbench-queries'

function summary(
  status: GenerationJobSummaryReadDto['status'],
): GenerationJobSummaryReadDto {
  return {
    generation_job_id: `job-${status}`,
    model_id: 'model-1',
    model_code: 'gpt-image-2',
    model_display_name: 'GPT Image 2',
    work_mode: 'INSTANT',
    mode: 'NORMAL_GENERATION',
    compress_output_under_1000kb: false,
    status,
    input_summary: { count: 1, primary_name: '商品图' },
    created_by_display_name: '用户',
    created_at: '2026-09-06T00:00:00Z',
    updated_at: '2026-09-06T00:00:00Z',
    total_count: 1,
    pending_count: status === 'PENDING' ? 1 : 0,
    running_count: status === 'RUNNING' ? 1 : 0,
    success_count: status === 'SUCCESS' ? 1 : 0,
    failed_count: status === 'FAILED' ? 1 : 0,
  }
}

function page(
  statuses: GenerationJobSummaryReadDto['status'][],
): GenerationJobPageDto {
  return {
    items: statuses.map(summary),
    total: statuses.length,
    page: 1,
    page_size: 20,
  }
}

describe('generation polling', () => {
  it('polls only non-terminal job details', () => {
    expect(generationJobPollingInterval('PENDING')).toBe(1_500)
    expect(generationJobPollingInterval('RUNNING')).toBe(1_500)
    expect(generationJobPollingInterval('SUCCESS')).toBe(false)
    expect(generationJobPollingInterval('PARTIAL_FAILED')).toBe(false)
    expect(generationJobPollingInterval('FAILED')).toBe(false)
    expect(generationJobPollingInterval(undefined)).toBe(false)
  })

  it('polls record pages while any listed job is active', () => {
    expect(generationJobListPollingInterval(page(['SUCCESS', 'RUNNING']))).toBe(
      2_000,
    )
    expect(
      generationJobListPollingInterval(
        page(['SUCCESS', 'PARTIAL_FAILED', 'FAILED']),
      ),
    ).toBe(false)
    expect(generationJobListPollingInterval(undefined)).toBe(false)
  })
})
