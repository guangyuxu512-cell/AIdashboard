import type {
  MerchantExperienceScore,
  OperatingDashboardRecord,
} from '../model/types'
import { formatShanghaiDate, listCalendarDates, shiftCalendarDate } from '../model/dashboard'

interface ShopSeed {
  shopId: string
  shopName: string
  platform: 'douyin' | 'pdd'
  dailyTurnoverCents: number
  dailyOrders: number
  dailyReturns: number
  score: number | null
}

const SHOP_SEEDS: ShopSeed[] = [
  {
    shopId: 'dashboard-shop-001',
    shopName: 'HuanYu',
    platform: 'douyin',
    dailyTurnoverCents: 328_640,
    dailyOrders: 151,
    dailyReturns: 8,
    score: 81,
  },
  {
    shopId: 'dashboard-shop-002',
    shopName: 'MyCookLab',
    platform: 'douyin',
    dailyTurnoverCents: 200_000,
    dailyOrders: 95,
    dailyReturns: 4,
    score: 90,
  },
  {
    shopId: 'dashboard-shop-003',
    shopName: '示例店铺 A',
    platform: 'pdd',
    dailyTurnoverCents: 80_000,
    dailyOrders: 40,
    dailyReturns: 2,
    score: null,
  },
  {
    shopId: 'dashboard-shop-004',
    shopName: '示例店铺 B',
    platform: 'pdd',
    dailyTurnoverCents: 70_000,
    dailyOrders: 30,
    dailyReturns: 1,
    score: null,
  },
  {
    shopId: 'dashboard-shop-005',
    shopName: '示例店铺 C',
    platform: 'douyin',
    dailyTurnoverCents: 60_000,
    dailyOrders: 25,
    dailyReturns: 1,
    score: 86,
  },
  {
    shopId: 'dashboard-shop-006',
    shopName: '示例店铺 D',
    platform: 'douyin',
    dailyTurnoverCents: 50_000,
    dailyOrders: 20,
    dailyReturns: 1,
    score: 88,
  },
  {
    shopId: 'dashboard-shop-007',
    shopName: '示例店铺 E',
    platform: 'pdd',
    dailyTurnoverCents: 30_000,
    dailyOrders: 15,
    dailyReturns: 1,
    score: null,
  },
  {
    shopId: 'dashboard-shop-008',
    shopName: '示例店铺 F',
    platform: 'pdd',
    dailyTurnoverCents: 24_040,
    dailyOrders: 10,
    dailyReturns: 0,
    score: null,
  },
  {
    shopId: 'dashboard-shop-009',
    shopName: '长名称经营数据演示店铺（华东旗舰店）',
    platform: 'douyin',
    dailyTurnoverCents: 17_600,
    dailyOrders: 8,
    dailyReturns: 0,
    score: 84,
  },
  {
    shopId: 'dashboard-shop-010',
    shopName: '示例店铺 G',
    platform: 'pdd',
    dailyTurnoverCents: 14_520,
    dailyOrders: 6,
    dailyReturns: 0,
    score: null,
  },
  {
    shopId: 'dashboard-shop-011',
    shopName: '待恢复同步店铺',
    platform: 'douyin',
    dailyTurnoverCents: 11_280,
    dailyOrders: 5,
    dailyReturns: 1,
    score: 79,
  },
  {
    shopId: 'dashboard-shop-012',
    shopName: '示例店铺 H',
    platform: 'pdd',
    dailyTurnoverCents: 8_600,
    dailyOrders: 4,
    dailyReturns: 0,
    score: null,
  },
]

// Keep the development-only trend visibly non-flat. The small per-shop offset
// below still makes rows differ without changing the meaning of this fixture.
const DAILY_TREND_VARIATION = [-5, -1, 2, -2, 1, 5, 3] as const

function buildExperience(
  seed: ShopSeed,
  businessDate: string,
): MerchantExperienceScore | null {
  if (seed.score === null) return null
  const offset = Number(businessDate.slice(-1)) % 3
  return {
    totalScore: seed.score,
    productScore: seed.score - 2 + offset,
    logisticsScore: seed.score + 1 - offset,
    serviceScore: seed.score + offset,
    collectedAt: `${businessDate}T08:05:00+08:00`,
  }
}

/** Explicit development fixture. It is never imported by Real API mode. */
export function createOperatingDashboardFixture(
  now = new Date(),
): OperatingDashboardRecord[] {
  const yesterday = shiftCalendarDate(formatShanghaiDate(now), -1)
  const dates = listCalendarDates({
    startDate: shiftCalendarDate(yesterday, -45),
    endDate: yesterday,
  })

  return dates.flatMap((businessDate, dayIndex) =>
    SHOP_SEEDS.flatMap((seed, shopIndex) => {
      // A controlled missing observation makes the chart's null-data behavior
      // visible when this shop/date is selected; it is not converted to zero.
      if (seed.shopId === 'dashboard-shop-011' && dayIndex % 9 === 0) return []

      const variation =
        DAILY_TREND_VARIATION[dayIndex % DAILY_TREND_VARIATION.length]! +
        ((shopIndex * 3) % 7) -
        3
      const turnoverCents = Math.max(
        0,
        seed.dailyTurnoverCents + variation * 1_140,
      )
      const orderCount = Math.max(0, seed.dailyOrders + (variation % 4))
      const refundOrderCount =
        seed.shopId === 'dashboard-shop-009' && dayIndex % 7 === 0
          ? null
          : Math.max(0, seed.dailyReturns + (variation < -2 ? 1 : 0))

      return [
        {
          shopId: seed.shopId,
          shopName: seed.shopName,
          platform: seed.platform,
          businessDate,
          turnoverCents,
          orderCount,
          refundOrderCount,
          experience: buildExperience(seed, businessDate),
          collectedAt: `${businessDate}T08:${String(5 + (shopIndex % 4)).padStart(2, '0')}:00+08:00`,
        },
      ]
    }),
  )
}
