import type {
  DashboardComparison,
  OperatingDashboardDateRange,
  OperatingDashboardFilters,
  OperatingDashboardRead,
  OperatingDashboardRecord,
  OperatingDashboardShopOption,
  OperatingDashboardSort,
  OperatingDashboardTableRow,
} from './types'

const SHANGHAI_TIME_ZONE = 'Asia/Shanghai'
const DASHBOARD_NAME_COLLATOR = new Intl.Collator('zh-CN')

function getDateParts(value: Date): Record<string, string> {
  return Object.fromEntries(
    new Intl.DateTimeFormat('en-US', {
      timeZone: SHANGHAI_TIME_ZONE,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    })
      .formatToParts(value)
      .filter((part) => part.type !== 'literal')
      .map((part) => [part.type, part.value]),
  )
}

/** Return a calendar date without depending on the host computer time zone. */
export function formatShanghaiDate(value: Date): string {
  const parts = getDateParts(value)
  return `${parts.year}-${parts.month}-${parts.day}`
}

function parseCalendarDate(value: string): number {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!match) throw new TypeError(`Invalid calendar date: ${value}`)
  return Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
}

function formatCalendarDate(value: number): string {
  return new Date(value).toISOString().slice(0, 10)
}

export function shiftCalendarDate(value: string, days: number): string {
  return formatCalendarDate(parseCalendarDate(value) + days * 86_400_000)
}

export function listCalendarDates(range: OperatingDashboardDateRange): string[] {
  const start = parseCalendarDate(range.startDate)
  const end = parseCalendarDate(range.endDate)
  if (end < start) return []

  const result: string[] = []
  for (let cursor = start; cursor <= end; cursor += 86_400_000) {
    result.push(formatCalendarDate(cursor))
  }
  return result
}

function dateRangeLength(range: OperatingDashboardDateRange): number {
  return listCalendarDates(range).length
}

export function resolveOperatingDashboardDateRange(
  filters: OperatingDashboardFilters,
  now = new Date(),
): OperatingDashboardDateRange {
  const yesterday = shiftCalendarDate(formatShanghaiDate(now), -1)

  if (filters.datePreset === 'custom' && filters.customDateRange) {
    const [first, second] = filters.customDateRange
    const firstDate = formatShanghaiDate(new Date(first))
    const secondDate = formatShanghaiDate(new Date(second))
    return firstDate <= secondDate
      ? { startDate: firstDate, endDate: secondDate }
      : { startDate: secondDate, endDate: firstDate }
  }

  const days =
    filters.datePreset === 'last3Days'
      ? 3
      : filters.datePreset === 'last7Days'
        ? 7
        : filters.datePreset === 'last30Days'
          ? 30
          : 1

  return {
    startDate: shiftCalendarDate(yesterday, -(days - 1)),
    endDate: yesterday,
  }
}

export function getPreviousOperatingDashboardDateRange(
  range: OperatingDashboardDateRange,
): OperatingDashboardDateRange {
  const days = dateRangeLength(range)
  return {
    startDate: shiftCalendarDate(range.startDate, -days),
    endDate: shiftCalendarDate(range.endDate, -days),
  }
}

function isInRange(value: string, range: OperatingDashboardDateRange): boolean {
  return value >= range.startDate && value <= range.endDate
}

function sumAvailable(values: ReadonlyArray<number | null>): number | null {
  let total = 0
  let hasValue = false
  for (const value of values) {
    if (value === null) continue
    hasValue = true
    total += value
  }
  return hasValue ? total : null
}

function compare(
  current: number | null,
  previous: number | null,
  lowerIsBetter = false,
): DashboardComparison {
  if (current === null || previous === null) return { state: 'unavailable' }
  if (current === previous) return { state: 'equal' }
  if (previous === 0) return { state: 'unavailable' }

  const increased = current > previous
  return {
    state: increased ? 'increase' : 'decrease',
    percentage: Math.abs(((current - previous) / previous) * 100),
    favorable: lowerIsBetter ? !increased : increased,
  }
}

function filteredRecords(
  records: ReadonlyArray<OperatingDashboardRecord>,
  range: OperatingDashboardDateRange,
  filters: OperatingDashboardFilters,
): OperatingDashboardRecord[] {
  return records.filter(
    (record) =>
      isInRange(record.businessDate, range) &&
      (filters.platform === null || record.platform === filters.platform) &&
      (filters.shopId === null || record.shopId === filters.shopId),
  )
}

function buildTableRows(
  records: ReadonlyArray<OperatingDashboardRecord>,
): OperatingDashboardTableRow[] {
  const groups = new Map<string, OperatingDashboardRecord[]>()
  for (const record of records) {
    const group = groups.get(record.shopId) ?? []
    group.push(record)
    groups.set(record.shopId, group)
  }

  return [...groups.values()]
    .map((group) => {
      const newest = [...group].sort((left, right) =>
        (right.collectedAt ?? '').localeCompare(left.collectedAt ?? ''),
      )[0]!
      const newestExperience = [...group]
        .filter((record) => record.experience !== null)
        .sort((left, right) =>
          (right.experience?.collectedAt ?? '').localeCompare(
            left.experience?.collectedAt ?? '',
          ),
        )[0]?.experience ?? null

      return {
        shopId: newest.shopId,
        shopName: newest.shopName,
        platform: newest.platform,
        turnoverCents: sumAvailable(group.map((record) => record.turnoverCents)),
        orderCount: sumAvailable(group.map((record) => record.orderCount)),
        returnQuantity: sumAvailable(
          group.map((record) => record.returnQuantity),
        ),
        experience: newestExperience,
        collectedAt: newest.collectedAt,
      }
    })
    .sort((left, right) => left.shopName.localeCompare(right.shopName, 'zh-CN'))
}

function compareShopIds(left: string, right: string): number {
  if (left === right) return 0
  return left < right ? -1 : 1
}

function compareNullableNumbers(
  left: number | null,
  right: number | null,
  direction: OperatingDashboardSort['direction'],
): number {
  if (left === null) return right === null ? 0 : 1
  if (right === null) return -1

  const comparison = left - right
  return direction === 'asc' ? comparison : -comparison
}

function parseCollectedAt(value: string | null): number | null {
  if (value === null) return null
  const timestamp = Date.parse(value)
  return Number.isFinite(timestamp) ? timestamp : null
}

/**
 * Sorts the already filtered UI-only result before it is paginated. The
 * default order remains the dashboard's Chinese shop-name order. Missing
 * values always remain after real values, and shop_id makes tied values stable.
 */
export function sortOperatingDashboardRows(
  rows: ReadonlyArray<OperatingDashboardTableRow>,
  sort: OperatingDashboardSort | null,
): OperatingDashboardTableRow[] {
  const activeSort: OperatingDashboardSort = sort ?? {
    field: 'shopName',
    direction: 'asc',
  }

  return [...rows].sort((left, right) => {
    let comparison: number
    switch (activeSort.field) {
      case 'shopName':
        comparison = DASHBOARD_NAME_COLLATOR.compare(
          left.shopName,
          right.shopName,
        )
        if (activeSort.direction === 'desc') comparison *= -1
        break
      case 'turnoverCents':
        comparison = compareNullableNumbers(
          left.turnoverCents,
          right.turnoverCents,
          activeSort.direction,
        )
        break
      case 'orderCount':
        comparison = compareNullableNumbers(
          left.orderCount,
          right.orderCount,
          activeSort.direction,
        )
        break
      case 'returnQuantity':
        comparison = compareNullableNumbers(
          left.returnQuantity,
          right.returnQuantity,
          activeSort.direction,
        )
        break
      case 'collectedAt':
        comparison = compareNullableNumbers(
          parseCollectedAt(left.collectedAt),
          parseCollectedAt(right.collectedAt),
          activeSort.direction,
        )
        break
    }
    return comparison === 0
      ? compareShopIds(left.shopId, right.shopId)
      : comparison
  })
}

function buildTrend(
  records: ReadonlyArray<OperatingDashboardRecord>,
  range: OperatingDashboardDateRange,
) {
  return listCalendarDates(range).map((businessDate) => {
    const dailyRecords = records.filter(
      (record) => record.businessDate === businessDate,
    )
    return {
      businessDate,
      turnoverCents: sumAvailable(
        dailyRecords.map((record) => record.turnoverCents),
      ),
      orderCount: sumAvailable(dailyRecords.map((record) => record.orderCount)),
    }
  })
}

function buildAvailableShopOptions(
  records: ReadonlyArray<OperatingDashboardRecord>,
): OperatingDashboardShopOption[] {
  const shops = new Map<string, OperatingDashboardShopOption>()
  for (const record of records) {
    shops.set(record.shopId, {
      shopId: record.shopId,
      shopName: record.shopName,
      platform: record.platform,
    })
  }
  return [...shops.values()].sort((left, right) =>
    left.shopName.localeCompare(right.shopName, 'zh-CN'),
  )
}

/**
 * Builds the entire filtered result before pagination. This is deliberate for
 * the UI-only source: cards, trends and the table must share one filter scope.
 */
export function buildOperatingDashboardRead(
  records: ReadonlyArray<OperatingDashboardRecord>,
  filters: OperatingDashboardFilters,
  now = new Date(),
): OperatingDashboardRead {
  const dateRange = resolveOperatingDashboardDateRange(filters, now)
  const comparisonDateRange = getPreviousOperatingDashboardDateRange(dateRange)
  const trendDateRange =
    filters.datePreset === 'yesterday'
      ? {
          startDate: shiftCalendarDate(dateRange.endDate, -6),
          endDate: dateRange.endDate,
        }
      : dateRange
  const current = filteredRecords(records, dateRange, filters)
  const previous = filteredRecords(records, comparisonDateRange, filters)
  const trendRecords = filteredRecords(records, trendDateRange, filters)
  const tableRows = buildTableRows(current)

  const currentTurnover = sumAvailable(
    current.map((record) => record.turnoverCents),
  )
  const previousTurnover = sumAvailable(
    previous.map((record) => record.turnoverCents),
  )
  const currentOrders = sumAvailable(current.map((record) => record.orderCount))
  const previousOrders = sumAvailable(
    previous.map((record) => record.orderCount),
  )
  const currentReturns = sumAvailable(
    current.map((record) => record.returnQuantity),
  )
  const previousReturns = sumAvailable(
    previous.map((record) => record.returnQuantity),
  )

  const allAvailableShops = buildAvailableShopOptions(records)

  return {
    dateRange,
    comparisonDateRange,
    trendDateRange,
    allAvailableShops,
    availableShops: allAvailableShops.filter(
      (shop) => filters.platform === null || shop.platform === filters.platform,
    ),
    summary: {
      turnoverCents: currentTurnover,
      orderCount: currentOrders,
      returnQuantity: currentReturns,
      shopCount: new Set(tableRows.map((row) => row.shopId)).size,
      turnoverComparison: compare(currentTurnover, previousTurnover),
      orderComparison: compare(currentOrders, previousOrders),
      returnComparison: compare(currentReturns, previousReturns, true),
      shopCountComparison: { state: 'unavailable' },
    },
    trend: buildTrend(trendRecords, trendDateRange),
    tableRows,
  }
}

/**
 * Keeps the dashboard chrome truthful before an operating-data Read Contract
 * exists. Shop identity comes from the existing authorized Shop query; every
 * operating metric and collection timestamp intentionally remains unavailable.
 */
export function buildOperatingDashboardUnavailableRead(
  filters: OperatingDashboardFilters,
  allAvailableShops: ReadonlyArray<OperatingDashboardShopOption>,
  tableShops: ReadonlyArray<OperatingDashboardShopOption>,
  shopCount: number | null,
  now = new Date(),
): OperatingDashboardRead {
  const dateRange = resolveOperatingDashboardDateRange(filters, now)
  const comparisonDateRange = getPreviousOperatingDashboardDateRange(dateRange)
  const trendDateRange =
    filters.datePreset === 'yesterday'
      ? {
          startDate: shiftCalendarDate(dateRange.endDate, -6),
          endDate: dateRange.endDate,
        }
      : dateRange

  return {
    dateRange,
    comparisonDateRange,
    trendDateRange,
    allAvailableShops: [...allAvailableShops],
    availableShops: allAvailableShops.filter(
      (shop) => filters.platform === null || shop.platform === filters.platform,
    ),
    summary: {
      turnoverCents: null,
      orderCount: null,
      returnQuantity: null,
      shopCount,
      turnoverComparison: { state: 'unavailable' },
      orderComparison: { state: 'unavailable' },
      returnComparison: { state: 'unavailable' },
      shopCountComparison: { state: 'unavailable' },
    },
    trend: listCalendarDates(trendDateRange).map((businessDate) => ({
      businessDate,
      turnoverCents: null,
      orderCount: null,
    })),
    tableRows: tableShops.map((shop) => ({
      ...shop,
      turnoverCents: null,
      orderCount: null,
      returnQuantity: null,
      experience: null,
      collectedAt: null,
    })),
  }
}

export function formatOperatingDashboardDateRange(
  range: OperatingDashboardDateRange,
): string {
  if (range.startDate === range.endDate) return range.endDate
  return `${range.startDate} 至 ${range.endDate}`
}
