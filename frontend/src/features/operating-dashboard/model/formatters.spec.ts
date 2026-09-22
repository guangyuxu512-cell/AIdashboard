import { describe, expect, it } from 'vitest'

import { formatMerchantExperience } from './formatters'

describe('formatMerchantExperience', () => {
  it('keeps an unavailable platform score visibly unavailable', () => {
    expect(formatMerchantExperience(null)).toBe('—')
  })

  it('formats only the confirmed score dimensions on one line', () => {
    expect(
      formatMerchantExperience({
        totalScore: 81,
        productScore: 78,
        logisticsScore: 83,
        serviceScore: 83,
        collectedAt: '2026-09-20T08:05:00+08:00',
      }),
    ).toBe('81分 商品78 · 物流83 · 服务83')
  })
})
